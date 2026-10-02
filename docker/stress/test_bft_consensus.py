"""
BFT Consensus Stress Test — indirect throughput measurement via HTTP API.

How it works:
  Stress tester cannot send raw ZMQ/BFT messages (different internal network).
  Instead, it uses HTTP API to send events and monitor block growth to infer
  BFT pipeline throughput.

Environment:
  - Docker Compose: 4 nodes (node1-4), gateway
  - K8s: single NodePort endpoint

The generic test chain uses proof_of_authority. Node recovery is checked via
ledger readiness and chain stats; this does not prove BFT protocol view changes.
"""

import time
import logging
import os
import pytest
import requests
from urllib3.util import Timeout

from docker.stress.real_stress_client import (
    RealStressClient,
    REAL_REQUESTS,
    generate_event,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="BFT consensus tests require REAL_REQUESTS=true"
)

BFT_CHAIN = os.getenv("BFT_CHAIN_NAME", "bft_stress_test")


def _first_healthy_response(
    client: RealStressClient, method: str, path: str, **kwargs
) -> requests.Response | None:
    """Make HTTP request to first healthy node. Returns response or None."""
    for nid, st in client.node_status.items():
        if st.is_healthy:
            try:
                return client.session.request(method, f"{st.url}{path}", **kwargs)
            except Exception:
                continue
    return None


def get_chain_stats(client: RealStressClient, node_id: str, timeout: float = 10) -> dict[str, int]:
    """Read committed block and event counts on a node."""
    status = client.node_status[node_id]
    resp = client.session.get(
        f"{status.url}/api/ledger/chains/{BFT_CHAIN}/stats", timeout=Timeout(total=timeout),
    )
    assert resp.status_code == 200, f"Cannot read chain stats on {node_id}: HTTP {resp.status_code}"
    return resp.json()


def get_chain_list(client: RealStressClient) -> list[dict]:
    """Get chain list from the first healthy node."""
    resp = _first_healthy_response(client, "GET", "/api/ledger/chains", timeout=10)
    return resp.json() if resp and resp.status_code == 200 else []


def create_bft_chain(client: RealStressClient) -> bool:
    """Prepare the dedicated chain on every configured target node."""
    return client.create_chains_on_nodes(BFT_CHAIN)


class TestBFTThroughput:
    """Measure generic PoA chain throughput by monitoring block growth."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        assert self.client.wait_for_nodes(timeout=30), "Configured nodes did not become ledger-ready"
        assert create_bft_chain(self.client), "Could not prepare BFT chain on every target node"

    def _wait_for_committed_events(self, node_id: str, before: dict[str, int], sent: int) -> int:
        """Drain accepted events before a subsequent test restarts this node."""
        assert sent > 0, "No events were accepted"
        deadline = time.monotonic() + 120
        new_blocks = committed = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            after = get_chain_stats(self.client, node_id, timeout=min(10, remaining))
            new_blocks = after["total_blocks"] - before["total_blocks"]
            # This generic PoA chain appends one consensus event to each new block.
            committed = after["total_events"] - before["total_events"] - new_blocks
            if new_blocks > 0 and committed >= sent:
                return new_blocks
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        assert new_blocks > 0, "Accepted events must produce committed blocks"
        raise AssertionError(f"Only {committed}/{sent} accepted events committed within 120s on {node_id}")

    def test_poa_throughput_baseline(self):
        """Baseline: measure throughput with proof_of_authority (default consensus)."""
        # Get block count before
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        assert len(healthy) >= 1, "No healthy nodes"

        node_id = healthy[0]
        before = get_chain_stats(self.client, node_id)
        logger.info("Blocks before: %d", before["total_blocks"])

        # Send events for 30s
        duration = 30
        start = time.monotonic()
        end_time = start + duration
        sent = 0
        while time.monotonic() < end_time:
            event = generate_event()
            if self.client.submit_event(node_id, event, chain_name=BFT_CHAIN):
                sent += 1

        blocks_created = self._wait_for_committed_events(node_id, before, sent)
        throughput = sent / (time.monotonic() - start)

        logger.info("--- PoA Throughput Results ---")
        logger.info("Events sent: %d", sent)
        logger.info("Blocks created: %d", blocks_created)
        logger.info("Committed events/sec (including drain): %.2f", throughput)

    def test_events_per_block_ratio(self):
        """Measure events/block ratio to determine actual batch size."""
        node_id = next(
            (nid for nid, s in self.client.node_status.items() if s.is_healthy),
            None,
        )
        if not node_id:
            pytest.skip("No healthy nodes")

        before = get_chain_stats(self.client, node_id)

        batch_size = 100
        sent = 0
        for _ in range(batch_size):
            sent += bool(self.client.submit_event(node_id, generate_event(), chain_name=BFT_CHAIN))

        new_blocks = self._wait_for_committed_events(node_id, before, sent)

        logger.info("Events: %d, New blocks: %d, Ratio: %.1f events/block",
                     sent, new_blocks, sent / new_blocks)


@pytest.mark.stress
class TestBFTViewChange:
    """Check ledger availability and recovery after restarting the inferred primary."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        assert self.client.wait_for_nodes(timeout=30), "Configured nodes did not become ledger-ready"
        assert create_bft_chain(self.client), "Could not prepare BFT chain on every target node"

    def _find_healthy(self) -> list[str]:
        return [nid for nid, s in self.client.node_status.items() if s.is_healthy]

    def _infer_primary_node(self) -> str | None:
        sorted_nodes = sorted(self._find_healthy())
        return sorted_nodes[0] if sorted_nodes else None

    @staticmethod
    def _run_node_command(primary: str, action: str) -> None:
        import subprocess
        container_name = f"hierachain-{primary}"
        try:
            ns = os.environ.get("K8S_NAMESPACE")
            if ns and action == "stop":
                pod = primary.replace("node", "hierachain-node-")
                subprocess.run(["kubectl", "delete", "pod", "-n", ns, pod],
                               capture_output=True, timeout=15, check=True)
            elif ns:
                subprocess.run(["kubectl", "rollout", "restart", "deployment", "-n", ns],
                               capture_output=True, timeout=15, check=True)
            else:
                from docker.stress.docker_helper import run_docker_container_action
                docker_cmd = "stop" if action == "stop" else "start"
                stdout, stderr = run_docker_container_action(container_name, docker_cmd)
                if stderr:
                    raise RuntimeError(f"Failed to {action} {primary}: {stderr}")
                else:
                    logger.info("Successfully %s %s via helper: %s", action, primary, stdout)
        except Exception as e:
            logger.error("Failed to %s %s: %s", action, primary, e)
            raise

    def _check_node_recovered(self, node_id: str, deadline: float) -> bool:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self.client.check_health(node_id, timeout=min(3, remaining)):
            return False
        status = self.client.node_status.get(node_id)
        if not status:
            return False
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        try:
            resp = self.client.session.get(
                f"{status.url}/api/ledger/chains/{BFT_CHAIN}/stats",
                timeout=Timeout(total=min(5, remaining)),
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _poll_recovery(self, node_ids: list[str], start: float) -> float | None:
        assert node_ids, "Recovery requires at least one target node"
        deadline = start + 60
        while time.monotonic() < deadline:
            if all(self._check_node_recovered(nid, deadline) for nid in node_ids):
                elapsed = time.monotonic() - start
                return elapsed if elapsed < 60 else None
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        return None

    def test_view_change_recovery_time(self):
        """Kill primary, measure cluster recovery time."""
        primary = self._infer_primary_node()
        if not primary:
            pytest.skip("Cannot determine primary node")

        logger.info("Inferred primary: %s", primary)
        healthy = self._find_healthy()
        others = [n for n in healthy if n != primary]

        event = generate_event()
        for nid in others:
            self.client.submit_event(nid, event, chain_name=BFT_CHAIN)

        logger.info("Killing primary node: %s", primary)
        try:
            self._run_node_command(primary, "stop")

            recovery_time = self._poll_recovery(others, time.monotonic())
            logger.info("Recovery time: %.2fs", recovery_time or -1)
            assert recovery_time is not None, "Cluster should recover after view change"
            assert recovery_time < 60, "Recovery should complete within 60s"
        finally:
            self._run_node_command(primary, "start")
        recovery_time = self._poll_recovery([primary], time.monotonic())
        assert recovery_time is not None, "Restarted primary must recover its ledger and chain within 60s"
        assert self.client.wait_for_nodes(timeout=30), "All configured nodes must be ledger-ready after recovery"
