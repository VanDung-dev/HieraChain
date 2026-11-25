"""
P2P Network Stress Test — indirect measurement via REST API + network chaos.

NOTE: Stress tester cannot send raw ZMQ messages (different internal network).
These tests:
  1. Use API /api/ledger/network/ping/{target} to measure RTT between nodes
  2. Use chaos_controller.py (tc) to inject network delay/loss
  3. Measure network degradation impact on event throughput

Environment:
  - Docker Compose: can tc exec into container
  - K8s: can kubectl exec tc
"""

import logging
import os
import subprocess
import time

import pytest

from docker.stress.real_stress_client import (
    REAL_REQUESTS,
    RealStressClient,
    generate_event,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="P2P network tests require REAL_REQUESTS=true"
)

P2P_CHAIN = os.getenv("P2P_CHAIN_NAME", "p2p_stress_test")


def _exec_tc(node_id: str, cmd: list[str]) -> str:
    """Execute tc command in container."""
    container = f"hierachain-{node_id}"
    try:
        if os.environ.get("K8S_NAMESPACE"):
            ns = os.environ["K8S_NAMESPACE"]
            pod = f"hierachain-node-{int(node_id.removeprefix('node')) - 1}"
            result = subprocess.run(
                ["kubectl", "exec", "-n", ns, pod, "--"] + cmd,
                capture_output=True, timeout=15,
            )
            if result.returncode != 0:
                return result.stderr.decode() or f"kubectl exec exited {result.returncode}"
            return ""
        from docker.stress.docker_helper import run_docker_exec
        _, error = run_docker_exec(container, cmd)
        return error
    except Exception as e:
        logger.debug("tc exec failed on %s: %s", node_id, e)
        return str(e)


def _apply_tc(node_id: str, cmd: list[str]) -> None:
    error = _exec_tc(node_id, cmd)
    if not error:
        return
    if "Operation not permitted" in error:
        pytest.skip(f"tc requires NET_ADMIN on {node_id}: {error}")
    raise RuntimeError(f"tc command failed on {node_id}: {error}")


def _inject_delay(node_id: str, ms: int = 200, jitter: int = 20) -> None:
    """Inject network delay."""
    _exec_tc(node_id, ["tc", "qdisc", "del", "dev", "eth0", "root"])
    _apply_tc(node_id, [
        "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
        "delay", f"{ms}ms", f"{jitter}ms", "distribution", "normal",
    ])
    logger.info("Injected %dms ±%dms delay on %s", ms, jitter, node_id)


def _inject_loss(node_id: str, loss_pct: int = 5) -> None:
    """Inject packet loss."""
    _exec_tc(node_id, ["tc", "qdisc", "del", "dev", "eth0", "root"])
    _apply_tc(node_id, [
        "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
        "loss", f"{loss_pct}%",
    ])
    logger.info("Injected %d%% loss on %s", loss_pct, node_id)


def _reset_network(node_id: str) -> None:
    """Reset network to default."""
    error = _exec_tc(node_id, ["tc", "qdisc", "del", "dev", "eth0", "root"])
    if error and "Cannot delete qdisc with handle of zero" not in error:
        logger.debug("Network reset on %s reported: %s", node_id, error)
    logger.info("Reset network on %s", node_id)


def _wait_healthy(client: RealStressClient, node_id: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if client.check_health(node_id, timeout=min(5.0, max(0.1, deadline - time.monotonic()))):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(2.0, remaining))


class TestP2PPing:
    """Test P2P ping RTT between nodes."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=2):
            pytest.skip("Need at least 2 nodes")

    def test_ping_between_nodes(self):
        """Ping from one node to another."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        assert len(healthy) >= 2

        source = healthy[0]
        targets = healthy[1:]

        status = self.client.node_status[source]
        for target in targets:
            try:
                resp = self.client.session.get(
                    f"{status.url}/api/ledger/network/ping/{target}",
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info("Ping %s → %s: %s", source, target, data)
                else:
                    logger.info("Ping %s → %s: HTTP %d",
                                 source, target, resp.status_code)
            except Exception as e:
                logger.info("Ping %s → %s failed: %s", source, target, e)

    def test_ping_self(self):
        """Ping self."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        nid = healthy[0]
        status = self.client.node_status[nid]
        try:
            resp = self.client.session.get(
                f"{status.url}/api/ledger/network/ping/{nid}",
                timeout=10,
            )
            logger.info("Ping self %s: HTTP %d %s", nid, resp.status_code, resp.text[:200])
        except Exception as e:
            logger.info("Ping self failed: %s", e)


@pytest.mark.stress
class TestNetworkDegradation:
    """Measure network degradation impact on the system."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=2):
            pytest.skip("Need at least 2 nodes")

    def _run_throughput_brief(self, duration: int = 10) -> dict:
        """Run brief throughput test."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            return {"sent": 0, "failed": 0, "eps": 0}

        node_id = healthy[0]
        end = time.time() + duration
        sent = 0
        failed = 0

        while time.time() < end:
            ok = self.client.submit_event(node_id, generate_event(), chain_name=P2P_CHAIN)
            if ok:
                sent += 1
            else:
                failed += 1

        return {
            "sent": sent,
            "failed": failed,
            "eps": sent / duration if duration else 0,
        }

    def test_impact_of_network_latency(self):
        """Compare throughput before/after injecting latency."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if len(healthy) < 2:
            pytest.skip("Need at least 2 nodes")

        target = healthy[1]

        # Baseline
        baseline = self._run_throughput_brief(duration=10)
        logger.info("Baseline throughput: %s", baseline)

        try:
            _inject_delay(target, ms=300, jitter=30)
            time.sleep(3)
            degraded = self._run_throughput_brief(duration=10)
        finally:
            _reset_network(target)

        logger.info("Under 300ms latency: %s", degraded)

        if baseline["eps"] > 0 and degraded["eps"] > 0:
            impact = (baseline["eps"] - degraded["eps"]) / baseline["eps"] * 100
            logger.info("Throughput impact: %.1f%% reduction", impact)

    def test_impact_of_packet_loss(self):
        """Compare throughput before/after injecting packet loss."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if len(healthy) < 2:
            pytest.skip("Need at least 2 nodes")

        target = healthy[1]

        # Baseline
        baseline = self._run_throughput_brief(duration=10)

        try:
            _inject_loss(target, loss_pct=5)
            time.sleep(3)
            degraded = self._run_throughput_brief(duration=10)
        finally:
            _reset_network(target)

        logger.info("Baseline: %s", baseline)
        logger.info("Under 5%% loss: %s", degraded)

    def test_recovery_after_network_cut(self):
        """Cut network completely, restore, verify system recovery."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if len(healthy) < 2:
            pytest.skip("Need at least 2 nodes")

        target = healthy[1]

        # Baseline
        self.client.submit_event(target, generate_event(), chain_name=P2P_CHAIN)

        try:
            _inject_loss(target, loss_pct=100)
            time.sleep(5)
            try:
                self.client.submit_event(target, generate_event(), chain_name=P2P_CHAIN)
            except Exception:
                pass
        finally:
            _reset_network(target)

        ok = _wait_healthy(self.client, target)
        status = self.client.node_status.get(target)
        assert ok, (
            f"Node {target} should be healthy after network recovery: "
            f"{status.last_error if status else 'unknown node'}"
        )
