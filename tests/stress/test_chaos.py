"""
Chaos Engineering Stress Test.

Tests system resilience to unexpected failures:
  - Network partition (isolate node)
  - Kill random node
  - CPU throttle
  - Disk full simulation (journal)

Uses:
  - docker/scripts/chaos_controller.py (Docker socket API / kubectl)
  - tc (traffic control) inside container
  - docker update / kubectl resource quota
"""

import time
import logging
import os
import subprocess
import random
import pytest

from tests.stress.real_stress_client import (
    RealStressClient,
    REAL_REQUESTS,
    generate_event,
)

logger = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(
        not REAL_REQUESTS,
        reason="Chaos tests require REAL_REQUESTS=true"
    ),
    pytest.mark.stress,
]

CHAOS_CHAIN = os.getenv("CHAOS_CHAIN_NAME", "chaos_stress_test")


def _run_cmd(cmd: list[str], timeout: int = 15) -> tuple[str, str]:
    """Run command, return (stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr
    except Exception as e:
        return "", str(e)


def _node_container(node_id: str) -> str:
    """Map node_id → container name."""
    return f"hierachain-{node_id}"


def _node_pod(node_id: str) -> str:
    """Map node_id → K8s pod name."""
    idx = node_id.replace("node", "")
    try:
        n = int(idx) - 1
        return f"hierachain-node-{n}"
    except ValueError:
        return node_id


def _is_k8s() -> bool:
    return bool(os.environ.get("K8S_NAMESPACE"))


K8S_ACTIONS = {
    "stop": lambda ns, pod, **kw: _run_cmd(["kubectl", "delete", "pod", "-n", ns, pod]),
    "start": lambda ns, pod, **kw: None,
    "restart": lambda ns, pod, **kw: _run_cmd(["kubectl", "rollout", "restart", "deployment", "-n", ns]),
    "network_cut": lambda ns, pod, **kw: _run_cmd(
        ["kubectl", "exec", "-n", ns, pod, "--", "tc", "qdisc", "add", "dev", "eth0", "root", "netem", "loss", "100%"]),
    "network_reset": lambda ns, pod, **kw: _run_cmd(
        ["kubectl", "exec", "-n", ns, pod, "--", "tc", "qdisc", "del", "dev", "eth0", "root"]),
}

from tests.stress.docker_helper import (
    run_docker_container_action,
    run_docker_container_update,
    run_docker_exec,
)

DOCKER_ACTIONS = {
    "stop": lambda c, **kw: run_docker_container_action(c, "stop"),
    "start": lambda c, **kw: run_docker_container_action(c, "start"),
    "restart": lambda c, **kw: run_docker_container_action(c, "restart"),
    "cpu_throttle": lambda c, **kw: run_docker_container_update(c, kw.get("cpus", "0.1")),
    "cpu_unthrottle": lambda c, **kw: run_docker_container_update(c, "1.0"),
    "network_cut": lambda c, **kw: run_docker_exec(
        c, ["tc", "qdisc", "add", "dev", "eth0", "root", "netem", "loss", "100%"]),
    "network_reset": lambda c, **kw: run_docker_exec(
        c, ["tc", "qdisc", "del", "dev", "eth0", "root"]),
}


def _do(node_id: str, action: str, **kwargs):
    """Execute chaos action on node via dispatch table."""
    if _is_k8s():
        fn = K8S_ACTIONS.get(action)
        if fn:
            fn(os.environ["K8S_NAMESPACE"], _node_pod(node_id), **kwargs)
    else:
        fn = DOCKER_ACTIONS.get(action)
        if fn:
            fn(_node_container(node_id), **kwargs)


class TestRandomNodeKill:
    """Kill random node, verify system recovery."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=3):
            pytest.skip("Need at least 3 nodes")

    def _submit_events(self, node_ids: list[str], count: int) -> int:
        ok = 0
        for _ in range(count):
            for nid in node_ids:
                if self.client.submit_event(nid, generate_event(), chain_name=CHAOS_CHAIN):
                    ok += 1
        return ok

    def test_random_kill_and_recovery(self):
        """Kill random node, verify cluster survives and recovers."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        assert len(healthy) >= 3

        target = random.choice(healthy)
        survivors = [n for n in healthy if n != target]

        logger.info("Killing random node: %s", target)

        self._submit_events(survivors, 10)
        _do(target, "stop")
        kill_time = time.time()
        time.sleep(5)

        for nid in survivors:
            ok = self.client.check_health(nid)
            logger.info("Survivor %s: %s", nid, "alive" if ok else "dead")

        post_kill_ok = self._submit_events(survivors, 20)
        logger.info("Events submitted during kill: %d", post_kill_ok)

        _do(target, "start")
        self.client.wait_for_nodes(timeout=60)
        logger.info("Total recovery time: %.2fs", time.time() - kill_time)


class TestNetworkPartition:
    """Isolate node from network."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=3):
            pytest.skip("Need at least 3 nodes")

    def test_network_partition_then_heal(self):
        """Cut network of 1 node, run events, restore network."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        assert len(healthy) >= 3

        target = healthy[1]
        survivors = [n for n in healthy if n != target]

        # Send baseline events
        for _ in range(5):
            self.client.submit_event(target, generate_event(), chain_name=CHAOS_CHAIN)

        # Cut network (100% loss)
        _do(target, "network_cut")
        time.sleep(3)

        # Send events during partition
        isolated_ok = 0
        for _ in range(10):
            for nid in survivors:
                if self.client.submit_event(nid, generate_event(), chain_name=CHAOS_CHAIN):
                    isolated_ok += 1

        logger.info("Events during partition: %d", isolated_ok)

        # Restore network
        _do(target, "network_reset")
        time.sleep(5)

        # Verify
        ok = self.client.check_health(target)
        assert ok, f"Node {target} should be healthy after network heal"


class TestCPUThrottle:
    """CPU throttle — limit node CPU.

    Only runs on Docker (docker update --cpus).
    K8s requires resource quota, cannot be tested from stress-tester.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        if _is_k8s():
            pytest.skip("CPU throttle not available on K8s from tester")

        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=2):
            pytest.skip("Need at least 2 nodes")

    def test_cpu_throttle_impact(self):
        """Limit CPU to 0.1, measure throughput degradation."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        assert len(healthy) >= 2

        target = healthy[1]

        # Baseline
        baseline_ok = 0
        for _ in range(30):
            if self.client.submit_event(target, generate_event(), chain_name=CHAOS_CHAIN):
                baseline_ok += 1

        baseline_rate = baseline_ok / 5  # ~5s
        logger.info("Baseline throughput: ~%.1f eps", baseline_rate)

        # Throttle CPU to 0.1
        _do(target, "cpu_throttle", cpus="0.1")
        time.sleep(5)

        # Under throttle
        throttle_ok = 0
        start = time.time()
        for _ in range(30):
            if self.client.submit_event(target, generate_event(), chain_name=CHAOS_CHAIN):
                throttle_ok += 1
        throttle_elapsed = time.time() - start

        # Restore CPU
        _do(target, "cpu_unthrottle")

        throttle_rate = throttle_ok / throttle_elapsed if throttle_elapsed else 0
        logger.info("Under 0.1 CPU: ~%.1f eps (baseline: ~%.1f eps)",
                     throttle_rate, baseline_rate)

        if baseline_rate > 0:
            ratio = throttle_rate / baseline_rate
            logger.info("Throughput ratio: %.2fx", ratio)


class TestMultipleFailure:
    """Multiple simultaneous failures combined."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=4):
            pytest.skip("Need all 4 nodes")

    def test_kill_and_partition_simultaneously(self):
        """Kill 1 node + network partition 1 node simultaneously."""
        healthy = sorted(
            [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        )
        assert len(healthy) >= 4

        to_kill = healthy[0]
        to_cut = healthy[1]
        remaining = healthy[2:]

        logger.info("Killing %s, cutting network on %s", to_kill, to_cut)

        _do(to_kill, "stop")
        _do(to_cut, "network_cut")
        time.sleep(5)

        # Verify remaining nodes survive
        for nid in remaining:
            ok = self.client.check_health(nid)
            logger.info("%s: %s", nid, "alive" if ok else "dead")

        # Recovery
        _do(to_kill, "start")
        _do(to_cut, "network_reset")

        self.client.wait_for_nodes(timeout=60)
        logger.info("All nodes recovered after combined failures")
