"""Regression checks for stress setup without touching a live cluster."""

import base64
import json
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


@pytest.mark.parametrize("pytest_exit,wait_exit", [(0, 0), (7, 0), (0, 9)])
def test_k8s_runner_propagates_failure_and_never_uses_compose(
    tmp_path: Path, pytest_exit: int, wait_exit: int,
) -> None:
    script = f"""
source {shlex.quote(str(COMMON))}
K8S=true; ENV=k8s; NAMESPACE=hierachain; DURATION=15
COMPOSE=forbidden_compose
kubectl() {{
  echo "$*" >> calls
  if [ "$1" = exec ]; then return {pytest_exit}; fi
  if [ "$1" = wait ]; then return {wait_exit}; fi
  return 0
}}
forbidden_compose() {{ echo COMPOSE_FALLBACK >> calls; return 0; }}
run_tests
"""
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    calls = (tmp_path / "calls").read_text()
    assert result.returncode == (1 if wait_exit else pytest_exit), result.stderr
    assert "COMPOSE_FALLBACK" not in calls
    assert "delete namespace" not in calls
    assert "delete pod stress-tester" in calls
    if not wait_exit:
        assert "env TEST_DURATION=15 /stress-scripts/run-stress.sh" in calls
        assert "k8s_stress_report.html log/report/k8s_stress_report.html" in calls
        assert "k8s_stress_report.xml log/report/k8s_stress_report.xml" in calls
    else:
        assert "exec" not in calls


def test_k8s_readiness_failure_prevents_continuing(tmp_path: Path) -> None:
    script = f"""
source {shlex.quote(str(COMMON))}
K8S=true; NAMESPACE=hierachain
kubectl() {{ echo "$*" >> calls; return 9; }}
wait_nodes_healthy
"""
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1
    assert (tmp_path / "calls").read_text().startswith("rollout status statefulset/ipfs")


@pytest.mark.parametrize("reuse", [False, True])
def test_k8s_stress_preserves_cluster_and_docker_identities(tmp_path: Path, reuse: bool) -> None:
    wrapper = tmp_path / "hierachain.sh"
    wrapper.write_text((COMMON.parents[1] / "hierachain.sh").read_text())
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/common.sh").write_text("""
set -e
init_env() { K8S=true; }
check_prereqs() { :; }
ensure_product_env() { :; }
ensure_keys() { :; }
generate_identities() { echo ROTATED_DOCKER_KEYS >> calls; return 99; }
down_cluster() { echo DELETED_NAMESPACE >> calls; return 99; }
build_image() { echo build >> calls; }
deploy_k8s() { echo deploy >> calls; }
wait_nodes_healthy() { echo readiness >> calls; }
connect_ipfs_swarm() { echo swarm >> calls; }
run_tests() { echo tests >> calls; }
""")
    args = ["bash", str(wrapper), "stress", "k8s"] + (["--reuse"] if reuse else [])
    result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert calls == (["readiness", "swarm", "tests"] if reuse else
                     ["build", "deploy", "readiness", "swarm", "tests"])


def test_k8s_redeploy_preserves_existing_secrets(tmp_path: Path) -> None:
    script = f"""
source {shlex.quote(str(COMMON))}
NAMESPACE=hierachain
kubectl() {{
  echo "$*" >> calls
  case "$*" in
    *jsonpath*) echo existing-trust ;;
  esac
  return 0
}}
uv() {{ echo ROTATED_KEYS >> calls; return 99; }}
deploy_k8s
"""
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text()
    assert "create secret" not in calls
    assert "ROTATED_KEYS" not in calls
    assert "apply -k docker/k8s/" in calls


def test_k8s_missing_identity_refuses_existing_ledger(tmp_path: Path) -> None:
    script = f"""
source {shlex.quote(str(COMMON))}
NAMESPACE=hierachain
kubectl() {{
  echo "$*" >> calls
  case "$*" in
    'get secret'*) return 1 ;;
    'get pvc'*) echo persistent-ledger ;;
  esac
  return 0
}}
uv() {{ echo ROTATED_KEYS >> calls; return 99; }}
deploy_k8s
"""
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1
    assert "Restore the node identity secret" in result.stdout
    assert "ROTATED_KEYS" not in (tmp_path / "calls").read_text()


@pytest.mark.parametrize("connect_exit", [0, 9])
def test_k8s_swarm_connection_failure_is_not_hidden(tmp_path: Path, connect_exit: int) -> None:
    script = f"""
source {shlex.quote(str(COMMON))}
K8S=true; KUBECTL=kubectl
kubectl() {{
  echo "$*" >> calls
  case "$*" in
    *'config Identity.PeerID') echo "peer-$2" ;;
    'get pod'*) echo 127.0.0.2 ;;
    *'swarm connect'*) return {connect_exit} ;;
  esac
  return 0
}}
connect_ipfs_swarm
"""
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == (1 if connect_exit else 0), result.stderr
    calls = (tmp_path / "calls").read_text()
    assert calls.count("swarm connect") == (1 if connect_exit else 12)


def test_generated_k8s_identities_leave_docker_files_untouched(tmp_path: Path) -> None:
    identity = tmp_path / "docker/nodes/node1/identity.json"
    identity.parent.mkdir(parents=True)
    identity.write_text("existing Docker identity")
    destination = tmp_path / "k8s-identities"
    generator = COMMON.parents[1] / "scripts/generate_node_identities.py"
    result = subprocess.run([sys.executable, str(generator), "--output-dir", str(destination)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert identity.read_text() == "existing Docker identity"
    for node in range(1, 5):
        assert (destination / f"node{node}" / "identity.json").is_file()
        assert (destination / f"node{node}" / "trusted_block_keys.json").is_file()



def test_legacy_k8s_trust_migration_preserves_signing_keys(tmp_path: Path) -> None:
    identities = [{"node_id": f"node{i + 1}", "signing_public_key": str(i) * 64,
                   "signing_key": "retained-private-key"} for i in range(4)]
    data = {f"node-{i}-identity": base64.b64encode(json.dumps(identity).encode()).decode()
            for i, identity in enumerate(identities)}
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"apiVersion": "v1", "kind": "Secret", "data": data,
                                  "metadata": {"name": "hierachain-node-identities"}}))
    script = f"""
source {shlex.quote(str(COMMON))}
NAMESPACE=hierachain
kubectl() {{
  case "$*" in
    *jsonpath*) return 0 ;;
    'get secret hierachain-node-identities'*' -o json') cat secret.json ;;
    'apply -f -') cat > updated-secret.json ;;
  esac
  return 0
}}
uv() {{ shift 2; {shlex.quote(sys.executable)} "$@"; }}
deploy_k8s
"""
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    updated = json.loads((tmp_path / "updated-secret.json").read_text())["data"]
    assert {key: updated[key] for key in data} == data
    trust = json.loads(base64.b64decode(updated["trusted-block-keys"]))
    assert trust == {identity["node_id"]: identity["signing_public_key"] for identity in identities}
    assert "retained-private-key" not in result.stdout + result.stderr



def test_docker_runner_passes_secret_via_environment(tmp_path: Path) -> None:
    key = "e" * 64
    script = f"""
source {shlex.quote(str(COMMON))}
K8S=false; ENV=docker; DURATION=15; COMPOSE=compose
IPFS_ENCRYPTION_KEY={key}
compose() {{
  printf '%s\\n' "$@" > arguments
  [ "$HRC_IPFS_ENCRYPTION_KEY" = "$IPFS_ENCRYPTION_KEY" ]
}}
run_tests
"""
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    arguments = (tmp_path / "arguments").read_text()
    assert "HRC_IPFS_ENCRYPTION_KEY" in arguments
    assert "TARGET_NODES=gateway:80,node1:2661,node2:2661,node3:2661,node4:2661" in arguments
    assert "TEST_DURATION=15" in arguments
    assert key not in arguments + result.stdout + result.stderr



def test_k8s_setup_summary_uses_cluster_addresses_and_persisted_token(tmp_path: Path) -> None:
    script = f"""
source {shlex.quote(str(COMMON))}
init_env k8s
EXPLORER_TOKEN=unused_fresh_token
print_setup_summary
"""
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert "http://localhost:32660/web2-status" in result.stdout
    assert "get secret hierachain-secrets" in result.stdout
    assert "node1 → hierachain-node-0.hierachain-node-headless:2661" in result.stdout
    assert "ipfs-3.ipfs-headless:5001" in result.stdout
    assert "WireGuard" not in result.stdout
    assert "unused_fresh_token" not in result.stdout
