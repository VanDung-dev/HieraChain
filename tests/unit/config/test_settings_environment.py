"""Regression coverage for environment capture and supported setting aliases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from hierachain.config.settings import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _run_settings_probe(
    working_directory: Path,
    variables: dict[str, str],
    script: str,
) -> subprocess.CompletedProcess[str]:
    """Run a fresh Python process with only task-specific HieraChain env values."""
    env = os.environ.copy()
    for name in tuple(env):
        if name.startswith("HRC_") or name in {
            "ENV", "DATABASE_URL", "NODE_ID", "NODE_PORT", "PEERS",
            "REDIS_HOST", "REDIS_PORT",
        }:
            env.pop(name)
    env.update({"HRC_AUTO_CONFIG": "false", **variables})
    python_path = [str(REPOSITORY_ROOT)]
    if env.get("PYTHONPATH"):
        python_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path)
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=working_directory,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_dotenv_is_loaded_before_settings_capture(tmp_path: Path) -> None:
    """Settings imported from a fresh working directory must see its .env values."""
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "HRC_ENV=production",
                "HRC_AUTH_ENABLED=true",
                "DATABASE_URL=postgresql://db.example:5432/ledger",
                "HRC_API_PORT=9011",
                "HRC_CORS_ORIGINS=https://portal.example",
                "HRC_AUTO_CONFIG=false",
            )
        ),
        encoding="utf-8",
    )
    result = _run_settings_probe(
        tmp_path,
        {},
        """
import json
from hierachain.config.settings import get_settings
settings = get_settings()
print(json.dumps({
    'database_url': settings.DATABASE_URL,
    'api_port': settings.API_PORT,
    'cors_origins': settings.CORS_ORIGINS,
}))
""",
    )

    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout.strip().splitlines()[-1])
    assert config == {
        "database_url": "postgresql://db.example:5432/ledger",
        "api_port": 9011,
        "cors_origins": ["https://portal.example"],
    }


def test_kubernetes_environment_aliases_are_read() -> None:
    """Legacy Kubernetes names map to node, peer, P2P-port, and Redis settings."""
    result = _run_settings_probe(
        REPOSITORY_ROOT,
        {
            "NODE_ID": "legacy-node-2",
            "NODE_PORT": "5002",
            "PEERS": "node1@node1:5001, node3@node3:5003",
            "HRC_REDIS_HOST": "redis.hierachain.svc",
            "HRC_REDIS_PORT": "6380",
        },
        """
import json
from hierachain.config.settings import Settings
print(json.dumps({
    'node_id': Settings.NODE_ID,
    'p2p_port': Settings.P2P_PORT,
    'peers': Settings.P2P_PEERS,
    'redis_host': Settings.REDIS_HOST,
    'redis_port': Settings.REDIS_PORT,
}))
""",
    )

    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout.strip().splitlines()[-1])
    assert config == {
        "node_id": "legacy-node-2",
        "p2p_port": 5002,
        "peers": ["node1@node1:5001", "node3@node3:5003"],
        "redis_host": "redis.hierachain.svc",
        "redis_port": 6380,
    }


def test_kubernetes_deployment_peer_seeds_include_runtime_node_ids() -> None:
    manifest = (REPOSITORY_ROOT / "docker/k8s/node-deployment.yaml").read_text()
    for seed_list in (
        "node2@hierachain-node2:5002,node3@hierachain-node3:5003,"
        "node4@hierachain-node4:5004",
        "node1@hierachain-node1:5001,node3@hierachain-node3:5003,"
        "node4@hierachain-node4:5004",
        "node1@hierachain-node1:5001,node2@hierachain-node2:5002,"
        "node4@hierachain-node4:5004",
        "node1@hierachain-node1:5001,node2@hierachain-node2:5002,"
        "node3@hierachain-node3:5003",
    ):
        assert f'value: "{seed_list}"' in manifest


def test_cli_default_node_configuration_uses_settings_value() -> None:
    from click.testing import CliRunner

    from hierachain.cli import hrc

    result = CliRunner().invoke(hrc, ["--help"])

    assert result.exit_code == 0
    assert "data/config.yaml" in result.output
    assert Settings.CLI_CONFIG_FILE == "data/config.yaml"


def test_unsupported_master_key_settings_fail_closed() -> None:
    """Unimplemented provider and file selections must be rejected explicitly."""
    unsupported_settings = (
        {"HRC_MASTER_KEY_SOURCE": "vault"},
        {"HRC_MASTER_KEY_SOURCE": "file"},
        {"HRC_MASTER_KEY_FILE": "/tmp/unused-master-key"},
    )
    for variables in unsupported_settings:
        with patch.dict(os.environ, variables, clear=True):
            with pytest.raises(ValueError, match="Unsupported master-key configuration"):
                Settings()


def test_environment_master_key_alias_remains_accepted() -> None:
    """Keep the existing environment-secret behavior while dropping unused metadata."""
    with patch.dict(os.environ, {"HRC_MASTER_KEY_SOURCE": "env"}, clear=True):
        assert "master_key" not in Settings.get_auth_config()
