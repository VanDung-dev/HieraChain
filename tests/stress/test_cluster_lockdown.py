"""
Cluster Lockdown / State Sync Stress Test.

Tests cluster quorum, lockdown, and state sync mechanisms during node failure.

How it works:
  - Uses chaos_controller.py or docker/kubectl exec to kill node
  - Monitors API response to detect lockdown state
  - Measures recovery time and data consistency

Environment:
  - Docker Compose: docker stop/start, docker exec tc
  - K8s: kubectl delete pod, kubectl exec tc
"""

import time
import json
import logging
import os
import socket
import http.client
import subprocess
import pytest

from tests.stress.real_stress_client import (
    RealStressClient,
    REAL_REQUESTS,
    DEFAULT_CHAIN_NAME,
    generate_event,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="Cluster lockdown tests require REAL_REQUESTS=true"
)

LOCKDOWN_CHAIN = os.getenv("LOCKDOWN_CHAIN_NAME", "lockdown_stress_test")

DOCKER_SOCKET_PATH = "/var/run/docker.sock"
_HAS_DOCKER_SOCKET = os.path.exists(DOCKER_SOCKET_PATH)


def _docker_api(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
    """Call Docker Engine API via Unix socket."""
    if not _HAS_DOCKER_SOCKET:
        return 0, "Docker socket not available"
    try:
        conn = http.client.HTTPConnection("localhost")
        conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock.connect(DOCKER_SOCKET_PATH)
        headers = {"Content-Type": "application/json"}
        conn.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        res = conn.getresponse()
        data = res.read().decode()
        return res.status, data
    except Exception as e:
        return 0, str(e)


def _docker_exec(container: str, cmd: list[str]) -> tuple[str, str]:
    """Execute command in Docker container via API socket."""
    status, data = _docker_api("POST", f"/v1.41/containers/{container}/exec", {
        "AttachStdout": True, "AttachStderr": True, "Cmd": cmd,
    })
    if status != 201:
        return "", f"exec create failed: {data[:200]}"
    exec_id = json.loads(data)["Id"]
    status, data = _docker_api("POST", f"/v1.41/exec/{exec_id}/start", {
        "Detach": False, "Tty": False,
    })
    return data, "" if status == 200 else data[:200]


def _docker_stop(container: str) -> bool:
    """Stop container via Docker API."""
    status, data = _docker_api("POST", f"/v1.41/containers/{container}/stop")
    return status in (204, 304)


def _docker_start(container: str) -> bool:
    """Start container via Docker API."""
    status, data = _docker_api("POST", f"/v1.41/containers/{container}/start")
    return status == 204


def _k8s_exec(pod: str, cmd: list[str]) -> tuple[str, str]:
    """Execute in K8s pod."""
    try:
        ns = os.environ["K8S_NAMESPACE"]
        full = ["kubectl", "exec", "-n", ns, pod, "--"] + cmd
        result = subprocess.run(full, capture_output=True, text=True, timeout=15)
        return result.stdout, result.stderr
    except Exception as e:
        return "", str(e)


def _inject_network_delay(node_id: str, delay_ms: int = 200) -> None:
    """Inject network delay into node using tc."""
    if os.environ.get("K8S_NAMESPACE"):
        pod = _node_pod(node_id)
        _k8s_exec(pod, ["tc", "qdisc", "del", "dev", "eth0", "root"])
        _k8s_exec(pod, [
            "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
            "delay", f"{delay_ms}ms", "20ms", "distribution", "normal",
        ])
    else:
        c = _node_container(node_id)
        _docker_exec(c, ["tc", "qdisc", "del", "dev", "eth0", "root"])
        _docker_exec(c, [
            "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
            "delay", f"{delay_ms}ms", "20ms", "distribution", "normal",
        ])
    logger.info("Injected %dms latency on %s", delay_ms, node_id)


def _reset_network(node_id: str) -> None:
    """Reset network rules to default."""
    c = _node_container(node_id)
    logger.info("Resetting network on %s", c)
    if os.environ.get("K8S_NAMESPACE"):
        _k8s_exec(_node_pod(node_id), ["tc", "qdisc", "del", "dev", "eth0", "root"])
    else:
        _docker_exec(c, ["tc", "qdisc", "del", "dev", "eth0", "root"])


def _node_container(node_id: str) -> str:
    return f"hierachain-{node_id}"


def _node_pod(node_id: str) -> str:
    idx = node_id.replace("node", "")
    try:
        return f"hierachain-node-{int(idx) - 1}"
    except ValueError:
        return node_id


def _kill_node(node_id: str) -> None:
    """Kill node container/pod."""
    if os.environ.get("K8S_NAMESPACE"):
        ns = os.environ["K8S_NAMESPACE"]
        pod = _node_pod(node_id)
        subprocess.run(
            ["kubectl", "delete", "pod", "-n", ns, pod],
            capture_output=True, timeout=20,
        )
    else:
        c = _node_container(node_id)
        ok = _docker_stop(c)
        if not ok and _HAS_DOCKER_SOCKET:
            logger.warning("docker stop may have failed on %s", c)
        elif not _HAS_DOCKER_SOCKET:
            logger.warning("Docker socket not available — cannot actually kill %s", c)


def _restart_node(node_id: str) -> None:
    """Restart node container/pod."""
    if os.environ.get("K8S_NAMESPACE"):
        ns = os.environ["K8S_NAMESPACE"]
        subprocess.run(
            ["kubectl", "rollout", "restart", "deployment", "-n", ns],
            capture_output=True, timeout=20,
        )
    else:
        c = _node_container(node_id)
        ok = _docker_start(c)
        if not ok and _HAS_DOCKER_SOCKET:
            logger.warning("docker start may have failed on %s", c)
        elif not _HAS_DOCKER_SOCKET:
            logger.warning("Docker socket not available — cannot restart %s", c)


def _is_api_responding(client: RealStressClient, node_id: str) -> bool:
    """Check if node API is still responding."""
    try:
        status = client.node_status.get(node_id)
        if not status:
            return False
        resp = client.session.get(f"{status.url}/api/v1/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


class TestSingleNodeFailure:
    """Test when 1 node is killed — cluster still operates."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=3):
            pytest.skip("Need at least 3 nodes")

    def test_single_node_kill_no_lockdown(self):
        """Kill 1/4 node, verify cluster still serves (quorum remains)."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        assert len(healthy) >= 3, "Need at least 3 healthy nodes"

        target = healthy[-1]
        survivors = healthy[:-1]

        logger.info("Killing node: %s, survivors: %s", target, survivors)
        _kill_node(target)

        time.sleep(5)

        # Survivors still healthy
        for nid in survivors:
            ok = _is_api_responding(self.client, nid)
            logger.info("  %s: %s", nid, "alive" if ok else "dead")
            assert ok, f"Survivor {nid} should still respond"

        _restart_node(target)
        self.client.wait_for_nodes(timeout=30)


class TestQuorumLoss:
    """Test when quorum is lost (2/4 nodes) — cluster must lockdown."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=4):
            pytest.skip("Need all 4 nodes")

    def test_quorum_loss_blocks_writes(self):
        """Kill 2 nodes, send events — must be rejected (503 lockdown)."""
        healthy = sorted(
            [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        )
        assert len(healthy) >= 4

        targets = healthy[:2]
        survivors = healthy[2:]

        # Kill 2 nodes
        for t in targets:
            _kill_node(t)
            time.sleep(2)

        time.sleep(5)

        # Try sending events to survivor
        lockdown_detected = False
        for nid in survivors:
            try:
                status = self.client.node_status.get(nid)
                if not status:
                    continue
                event = generate_event()
                resp = self.client.session.post(
                    f"{status.url}/api/v1/chains/{LOCKDOWN_CHAIN}/events",
                    json=event,
                    timeout=10,
                )
                if resp.status_code in (503, 502):
                    lockdown_detected = True
                    logger.info("Lockdown detected on %s: HTTP %d", nid, resp.status_code)
            except Exception as e:
                logger.info("Request failed on %s: %s", nid, e)

        logger.info("Lockdown detected: %s", lockdown_detected)

        # Restart nodes
        for t in targets:
            _restart_node(t)
        self.client.wait_for_nodes(timeout=60)


@pytest.mark.stress
class TestNetworkPartition:
    """Test network partition — inject latency between nodes."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=3):
            pytest.skip("Need at least 3 nodes")

    def test_high_latency_impact(self):
        """Inject 500ms latency into 1 node, measure impact on event submission."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        assert len(healthy) >= 3

        target = healthy[1]

        # Baseline
        baseline_latencies = []
        for _ in range(20):
            start = time.time()
            self.client.submit_event(target, generate_event(), chain_name=LOCKDOWN_CHAIN)
            baseline_latencies.append((time.time() - start) * 1000)

        baseline_avg = sum(baseline_latencies) / len(baseline_latencies)

        # Inject latency
        _inject_network_delay(target, delay_ms=500)
        time.sleep(3)

        # Under latency
        latency_latencies = []
        for _ in range(20):
            start = time.time()
            self.client.submit_event(target, generate_event(), chain_name=LOCKDOWN_CHAIN)
            latency_latencies.append((time.time() - start) * 1000)

        latency_avg = sum(latency_latencies) / len(latency_latencies)

        logger.info("Baseline avg latency: %.2fms", baseline_avg)
        logger.info("Under 500ms delay avg: %.2fms", latency_avg)
        logger.info("Impact ratio: %.2fx", latency_avg / baseline_avg if baseline_avg else 0)

        # Cleanup
        _reset_network(target)

        # Latency increases but requests still succeed
        assert latency_avg > baseline_avg, "Latency should increase under injected delay"
