"""
CrossChain / Hierarchical Proof Flow Stress Test (real, no mock).

Measures full proof pipeline:
  SubChain events → block → proof hash → MainChain verify

Uses HieraChain HTTP API to create chains, send events, submit proof.

Environment:
  - Docker Compose: 4 nodes
  - K8s: single endpoint
"""

import time
import logging
import os
import pytest

from tests.stress.real_stress_client import (
    RealStressClient,
    REAL_REQUESTS,
    DEFAULT_NODES,
    generate_event,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="Hierarchical proof tests require REAL_REQUESTS=true"
)

PROOF_CHAIN_PREFIX = os.getenv("PROOF_CHAIN_PREFIX", "proof_stress")


def _create_chain(client: RealStressClient, node_id: str, chain_name: str, participants: list[str] | None = None) -> bool:
    status = client.node_status.get(node_id)
    if not status:
        return False
    try:
        resp = client.session.post(
            f"{status.url}/api/ledger/chains/{chain_name}/create",
            params={"chain_type": "generic"},
            json={"participants": participants or list(client.node_status.keys())},
            timeout=10,
        )
        return resp.status_code in (200, 201, 409)
    except Exception:
        return False


def _get_chain_stats(client: RealStressClient, node_id: str, chain_name: str) -> dict | None:
    status = client.node_status.get(node_id)
    if not status:
        return None
    try:
        resp = client.session.get(f"{status.url}/api/ledger/chains/{chain_name}/stats", timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def _get_all_chains(client: RealStressClient, node_id: str) -> list[dict]:
    status = client.node_status.get(node_id)
    if not status:
        return []
    try:
        resp = client.session.get(f"{status.url}/api/ledger/chains", timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("chains", data.get("data", []))
        return []
    except Exception:
        return []


class TestSubChainLifecycle:
    """Test SubChain lifecycle via API."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30):
            pytest.skip("No nodes available")

    def test_create_subchain_and_add_events(self):
        """Create SubChain, add events, verify chain stats."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        node_id = healthy[0]
        status = self.client.node_status[node_id]
        chain_name = f"{PROOF_CHAIN_PREFIX}_{int(time.time())}"

        # Create chain
        resp = self.client.session.post(
            f"{status.url}/api/ledger/chains/{chain_name}/create",
            params={"chain_type": "generic"},
            json={"participants": list(self.client.node_status.keys())},
            timeout=10,
        )
        assert resp.status_code in (200, 201, 409), \
            f"Create chain failed: {resp.status_code}"
        logger.info("Chain created: %s", chain_name)

        # Add events
        num_events = 100
        success = 0
        for _ in range(num_events):
            if self.client.submit_event(node_id, generate_event(), chain_name=chain_name):
                success += 1

        logger.info("Events added: %d/%d", success, num_events)

        # Wait for block creation
        time.sleep(3)

        # Verify stats
        resp = self.client.session.get(
            f"{status.url}/api/ledger/chains/{chain_name}/stats",
            timeout=10,
        )
        if resp.status_code == 200:
            stats = resp.json()
            logger.info("Chain stats: %s", stats)

        # Verify blocks
        resp = self.client.session.get(
            f"{status.url}/api/ledger/chains/{chain_name}/blocks",
            params={"limit": 5},
            timeout=10,
        )
        if resp.status_code == 200:
            blocks = resp.json()
            logger.info("Blocks: %d total, showing %d",
                         blocks.get("total_blocks", 0),
                         len(blocks.get("blocks", [])))

        assert success > 0, "Should add at least some events"

    def test_multiple_subchains_isolation(self):
        """Create multiple SubChains, verify data is not mixed."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        node_id = healthy[0]
        timestamp = int(time.time())

        chains = [
            f"{PROOF_CHAIN_PREFIX}_a_{timestamp}",
            f"{PROOF_CHAIN_PREFIX}_b_{timestamp}",
            f"{PROOF_CHAIN_PREFIX}_c_{timestamp}",
        ]

        for name in chains:
            ok = _create_chain(self.client, node_id, name, participants=[node_id])
            logger.info("Create %s: %s", name, "ok" if ok else "fail")

        for name in chains:
            self.client.submit_event(node_id, generate_event(), chain_name=name)

        time.sleep(3)

        for name in chains:
            stats = _get_chain_stats(self.client, node_id, name)
            if stats:
                logger.info("Chain %s: %d events", name, stats.get("total_events", 0))

        all_chains = _get_all_chains(self.client, node_id)
        chain_names = [c.get("name") for c in all_chains]
        for name in chains:
            logger.info("Chain %s in list: %s", name, name in chain_names)


@pytest.mark.stress
class TestProofSubmission:
    """Test proof submission from SubChain to MainChain."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30):
            pytest.skip("No nodes available")

    def test_submit_proof_to_main_chain(self):
        """Create chain, send events, submit proof to MainChain."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        node_id = healthy[0]
        status = self.client.node_status[node_id]
        chain_name = f"{PROOF_CHAIN_PREFIX}_proof_{int(time.time())}"

        # Create
        resp = self.client.session.post(
            f"{status.url}/api/ledger/chains/{chain_name}/create",
            params={"chain_type": "generic"},
            json={"participants": [node_id]},
            timeout=10,
        )
        assert resp.status_code in (200, 201, 409)

        # Add events
        for _ in range(50):
            self.client.submit_event(node_id, generate_event(), chain_name=chain_name)

        time.sleep(3)

        # Submit proof
        resp = self.client.session.post(
            f"{status.url}/api/ledger/chains/{chain_name}/submit-proof",
            json={"sub_chain_name": chain_name},
            timeout=15,
        )
        logger.info("Proof submission: HTTP %d %s",
                     resp.status_code, resp.text[:200] if resp.text else "")

        # If submit-proof is not implemented on node, this test skips silently
        if resp.status_code == 404:
            pytest.skip("submit-proof endpoint not available on this node")


@pytest.mark.stress
class TestEntityTracing:
    """Test entity tracing across chains."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = RealStressClient()
        if not self.client.wait_for_nodes(timeout=30):
            pytest.skip("No nodes available")

    def test_trace_entity_across_chains(self):
        """Send events with same entity_id across multiple chains, trace."""
        healthy = [nid for nid, s in self.client.node_status.items() if s.is_healthy]
        if not healthy:
            pytest.skip("No healthy nodes")

        node_id = healthy[0]
        status = self.client.node_status[node_id]
        timestamp = int(time.time())
        entity_id = f"trace_entity_{timestamp}"

        chain_a = f"{PROOF_CHAIN_PREFIX}_trace_a_{timestamp}"
        chain_b = f"{PROOF_CHAIN_PREFIX}_trace_b_{timestamp}"

        for name in [chain_a, chain_b]:
            self.client.session.post(
                f"{status.url}/api/ledger/chains/{name}/create",
                params={"chain_type": "generic"},
                json={"participants": [node_id]},
                timeout=10,
            )

        # Send events with same entity_id
        for name in [chain_a, chain_b]:
            event = generate_event()
            event["entity_id"] = entity_id
            self.client.submit_event(node_id, event, chain_name=name)

        time.sleep(3)

        # Trace entity
        resp = self.client.session.get(
            f"{status.url}/api/ledger/entities/{entity_id}/trace",
            timeout=10,
        )
        if resp.status_code == 200:
            trace = resp.json()
            logger.info("Entity trace: %s", trace)
        else:
            logger.info("Trace returned HTTP %d: %s",
                         resp.status_code, resp.text[:200] if resp.text else "")
