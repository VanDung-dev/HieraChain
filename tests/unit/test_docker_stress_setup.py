"""Regression checks for stress setup without touching a live cluster."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from hierachain.serialization import dumps_json

COMMON = Path(__file__).resolve().parents[2] / "docker/lib/common.sh"


def test_ipfs_client_import_does_not_bootstrap_production_server(tmp_path: Path) -> None:
    root = COMMON.parents[2]
    script = """
import sys
from hierachain.api.storage.ipfs_client import IPFSClient
assert IPFSClient is not None
assert 'hierachain.api.server' not in sys.modules
try:
    from hierachain.api import create_app
except RuntimeError as error:
    assert 'HRC_API_KEYS_FILE' in str(error), str(error)
else:
    raise AssertionError('Production server accepted missing authentication configuration')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(root), "HRC_ENV": "production",
             "HRC_AUTH_ENABLED": "true", "HRC_API_KEYS_FILE": ""},
        capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_docker_stress_output_keeps_reports_and_hides_live_logs() -> None:
    source = COMMON.read_text(encoding="utf-8")
    command = source[source.index("pytest docker/stress/"):source.index('--junitxml=', source.index("pytest docker/stress/"))]
    assert "-v" in command
    assert "--log-cli-level" not in command
    assert "-o log_cli=false" in command
    assert "-o faulthandler_timeout=0" in command
    assert "--show-capture=no --tb=short" in command
    assert "--log-level=INFO" in command
    assert "--html=" in command


def test_wheel_build_discards_deleted_modules_and_rebuilds(tmp_path: Path) -> None:
    (tmp_path / "build/lib").mkdir(parents=True)
    (tmp_path / "build/lib/deleted.py").write_text("stale", encoding="utf-8")
    (tmp_path / "docker/dist").mkdir(parents=True)
    (tmp_path / "docker/dist/hierachain-old.whl").touch()
    (tmp_path / "hierachain").mkdir()
    source = tmp_path / "hierachain/kept.py"
    source.write_text("current", encoding="utf-8")
    uv = tmp_path / "uv"
    uv.write_text('#!/bin/sh\n[ "$1" = build ] || exit 1\ntouch docker/dist/hierachain-new.whl\n', encoding="utf-8")
    uv.chmod(0o700)
    result = subprocess.run(
        ["bash", "-c", f"source {shlex.quote(str(COMMON))}; build_wheel"],
        cwd=tmp_path, env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "build").exists()
    assert not (tmp_path / "docker/dist/hierachain-old.whl").exists()
    assert (tmp_path / "docker/dist/hierachain-new.whl").exists()
    assert source.read_text(encoding="utf-8") == "current"


@pytest.mark.parametrize("key", [None, "", "   ", "test-credential"])
def test_stress_key_guard_reads_compose_config_without_exposing_key(tmp_path: Path, key: str | None) -> None:
    config = tmp_path / "compose.json"
    config.write_bytes(dumps_json({
        "services": {"stress-tester": {"environment": {"HRC_API_KEY": key}}},
    }).encode("utf-8"))
    uv = tmp_path / "uv"
    uv.write_text(f'#!/bin/sh\nshift 3\nexec {shlex.quote(sys.executable)} "$@"\n', encoding="utf-8")
    uv.chmod(0o700)
    result = subprocess.run(
        ["bash", "-c", f"source {shlex.quote(str(COMMON))}; "
         f"compose() {{ cat {shlex.quote(str(config))}; }}; COMPOSE=compose; ensure_stress_api_key"],
        cwd=tmp_path, env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert (result.returncode == 0) == bool(key and key.strip())
    assert "test-credential" not in result.stdout + result.stderr
