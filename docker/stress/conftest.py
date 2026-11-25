"""
Pytest configuration for HieraChain stress testing suite.

Ensures project root and docker directory are on sys.path.
"""

import os
import sys

import pytest

_STRESS_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCAL_ONLY_MODULES = {
    "test_crypto_scale.py",
    "test_duration_config.py",
    "test_live_stress_contracts.py",
    "test_memory_leak_soak.py",
    "test_memory_pressure_sync.py",
}
_DOCKER_DIR = os.path.dirname(_STRESS_DIR)
_PROJECT_ROOT = os.path.dirname(_DOCKER_DIR)

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _DOCKER_DIR not in sys.path:
    sys.path.insert(0, _DOCKER_DIR)
if _STRESS_DIR not in sys.path:
    sys.path.insert(0, _STRESS_DIR)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Check the live cluster before stress tests mutate or load it."""
    environment = os.getenv("HRC_STRESS_ENV")
    if environment in ("docker", "k8s") and os.getenv("REAL_REQUESTS", "true").lower() == "true":
        from docker.stress.real_stress_client import RealStressClient

        try:
            client = RealStressClient()
            if environment == "k8s" and not client.wait_for_nodes(timeout=30, min_healthy=4):
                raise RuntimeError("K8s stress requires all four live node APIs to be ready")
            client.preflight_auth()
            if environment == "k8s" and os.getenv("HRC_IPFS_ENABLED", "false").lower() == "true":
                from hierachain.api.storage.ipfs_client import IPFSClient, IPFSError

                try:
                    with IPFSClient(ipfs_host=os.environ["HRC_IPFS_HOST"]) as ipfs:
                        ipfs.get_daemon_version()
                except IPFSError:
                    raise RuntimeError("K8s stress requires a reachable IPFS API") from None
        except RuntimeError as exc:
            raise pytest.UsageError(str(exc)) from None


@pytest.fixture(autouse=True)
def restore_live_cluster_between_tests(request: pytest.FixtureRequest):
    if os.path.basename(str(getattr(request.node, "path", ""))) in _LOCAL_ONLY_MODULES:
        yield
        return

    from docker.stress.cluster_guard import live_docker_enabled, restore_cluster

    if not live_docker_enabled():
        yield
        return

    restore_cluster()
    try:
        yield
    finally:
        restore_cluster()
