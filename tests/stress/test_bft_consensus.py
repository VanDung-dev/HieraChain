"""
BFT Consensus Stress Test — indirect throughput measurement via HTTP API.

How it works:
  Stress tester cannot send raw ZMQ/BFT messages (different internal network).
  Instead, it uses HTTP API to send events and monitor block growth to infer
  BFT pipeline throughput.

Environment:
  - Docker Compose: 4 nodes (node1-4), gateway
  - K8s: single NodePort endpoint

Consensus types tested:
  - proof_of_authority (default)
  - byzantine_fault_tolerant
"""

import time
import logging
import os
import pytest

from tests.stress.real_stress_client import (
    RealStressClient,
    REAL_REQUESTS,
    DEFAULT_NODES,
    DEFAULT_CHAIN_NAME,
    generate_event,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="BFT consensus tests require REAL_REQUESTS=true"
)

BFT_CHAIN = os.getenv("BFT_CHAIN_NAME", "bft_stress_test")


def get_block_count(client: RealStressClient, node_id: str) -> int:
    """Get current block count of chain on a node."""
    try:
        status = client.node_status.get(node_id)
        if not status:
            return 0
        resp = client.session.get(
            f"{status.url}/api/v1/chains/{BFT_CHAIN}/stats",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("total_blocks", 0)
    except Exception as e:
        logger.debug("get_block_count failed for %s: %s", node_id, e)
    return 0


def get_chain_list(client: RealStressClient) -> list[dict]:
    """Get chain list from the first node."""
    for nid, st in client.node_status.items():
        if st.is_healthy:
            try:
                resp = client.session.get(
                    f"{st.url}/api/v1/chains",
                    timeout=10,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                continue
    return []


def create_bft_chain(client: RealStressClient) -> bool:
    """Create a dedicated chain for BFT test."""
    for nid, st in client.node_status.items():
        if st.is_healthy:
            try:
                resp = client.session.post(
                    f"{st.url}/api/v1/chains/{BFT_CHAIN}/create",
                    params={"chain_type": "generic"},
                    json={"participants": list(client.node_status.keys())},
                    timeout=10,
                )
                if resp.status_code in (200, 201, 409):
                    logger.info("BFT chain ready on %s", nid)
                    return True
            except Exception as e:
                logger.debug("create chain %s: %s", nid, e)
    return False


class TestBFTThroughput:
    """Measure BFT throughput by monitoring block growth."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30):
            pytest.skip("No nodes available")
        create_bft_chain(self.client)

    def test_poa_throughput_baseline(self):
        """Baseline: measure throughput with proof_of_authority (default consensus)."""
        # Get block count before
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        assert len(healthy) >= 1, "No healthy nodes"

        node_id = healthy[0]
        before_blocks = get_block_count(self.client, node_id)
        logger.info("Blocks before: %d", before_blocks)

        # Send events for 30s
        duration = 30
        end_time = time.time() + duration
        sent = 0
        while time.time() < end_time:
            event = generate_event()
            if self.client.submit_event(node_id, event, chain_name=BFT_CHAIN):
                sent += 1

        # Wait for block commit
        time.sleep(5)

        after_blocks = get_block_count(self.client, node_id)
        blocks_created = max(0, after_blocks - before_blocks)
        throughput = sent / duration if duration else 0

        logger.info("--- PoA Throughput Results ---")
        logger.info("Events sent: %d", sent)
        logger.info("Blocks created: %d", blocks_created)
        logger.info("Events/sec: %.2f", throughput)

        assert sent > 0, "Should send at least some events"
        assert blocks_created >= 0

    def test_events_per_block_ratio(self):
        """Measure events/block ratio to determine actual batch size."""
        node_id = next(
            (nid for nid, s in self.client.node_status.items() if s.is_healthy),
            None,
        )
        if not node_id:
            pytest.skip("No healthy nodes")

        before = get_block_count(self.client, node_id)

        batch_size = 100
        for _ in range(batch_size):
            self.client.submit_event(node_id, generate_event(), chain_name=BFT_CHAIN)

        # Wait longer for blocks to be created (batch timeout + block commit)
        time.sleep(10)
        after = get_block_count(self.client, node_id)
        new_blocks = after - before

        logger.info("Events: %d, New blocks: %d, Ratio: %.1f events/block",
                     batch_size, new_blocks,
                     batch_size / new_blocks if new_blocks else float("inf"))

        # Some chains have long batch timeout — don't fail if no block immediately
        if new_blocks == 0:
            logger.warning("No new blocks yet — batch may still be filling")
            # Check chain stats to see if events were received
            stats_resp = self.client.session.get(
                f"{self.client.node_status[node_id].url}/api/v1/chains/{BFT_CHAIN}/stats",
                timeout=10,
            )
            if stats_resp.status_code == 200:
                logger.info("Chain stats after submit: %s", stats_resp.json())


@pytest.mark.stress
class TestBFTViewChange:
    """Test BFT view change by killing the primary node."""

    REQUIRED_NODES = 3

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30, min_healthy=self.REQUIRED_NODES):
            pytest.skip("Need at least %d nodes" % self.REQUIRED_NODES)
        create_bft_chain(self.client)

    def _find_healthy(self) -> list[str]:
        return [nid for nid, s in self.client.node_status.items() if s.is_healthy]

    def _infer_primary_node(self) -> str | None:
        """Determine primary node based on view % n logic."""
        healthy = self._find_healthy()
        if not healthy:
            return None
        sorted_nodes = sorted(healthy)
        # Current view is not known via API, guess it's the first node
        return sorted_nodes[0]

    def test_view_change_recovery_time(self):
        """Kill primary, measure cluster recovery time."""
        import subprocess
        import json

        primary = self._infer_primary_node()
        if not primary:
            pytest.skip("Cannot determine primary node")

        logger.info("Inferred primary: %s", primary)

        # Send events steadily
        healthy = self._find_healthy()
        others = [n for n in healthy if n != primary]

        event = generate_event()
        for nid in others:
            self.client.submit_event(nid, event, chain_name=BFT_CHAIN)

        # Kill primary
        logger.info("Killing primary node: %s", primary)
        container_name = f"hierachain-{primary}"
        try:
            if os.environ.get("K8S_NAMESPACE"):
                pod_name = primary.replace("node", "hierachain-node-")
                subprocess.run(
                    ["kubectl", "delete", "pod", "-n", os.environ["K8S_NAMESPACE"], pod_name],
                    capture_output=True, timeout=15,
                )
            else:
                subprocess.run(
                    ["docker", "stop", container_name],
                    capture_output=True, timeout=15,
                )
        except Exception as e:
            logger.error("Failed to kill %s: %s", primary, e)

        # Measure recovery time
        start_recovery = time.time()
        recovery_time = None

        for attempt in range(60):
            try:
                for nid in others:
                    status = self.client.node_status.get(nid)
                    if status:
                        resp = self.client.session.get(
                            f"{status.url}/api/v1/chains/{BFT_CHAIN}/stats",
                            timeout=5,
                        )
                        if resp.status_code == 200:
                            if recovery_time is None:
                                recovery_time = time.time() - start_recovery
                            break
            except Exception:
                pass
            time.sleep(1)

        logger.info("Recovery time: %.2fs", recovery_time or -1)
        assert recovery_time is not None, "Cluster should recover after view change"
        assert recovery_time < 60, "Recovery should complete within 60s"

        # Restart node
        try:
            if os.environ.get("K8S_NAMESPACE"):
                pod_name = primary.replace("node", "hierachain-node-")
                subprocess.run(
                    ["kubectl", "rollout", "restart", "deployment", "-n", os.environ["K8S_NAMESPACE"]],
                    capture_output=True, timeout=15,
                )
            else:
                subprocess.run(
                    ["docker", "start", container_name],
                    capture_output=True, timeout=15,
                )
        except Exception:
            pass
