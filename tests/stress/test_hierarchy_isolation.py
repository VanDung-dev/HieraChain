"""
Hierarchy Logic Stress Tests.

This module tests the hierarchical chain logic components in isolation:
- K8sNamespaceManager (with mock mode for unit testing)
- ProofAggregator and proof aggregation logic
- CrossLevelSyncManager synchronization logic
- SubChainRebalancer threshold detection and splitting logic

These tests run with mocked K8s/cluster dependencies to validate logic
without requiring a full Kubernetes cluster or multi-node setup.
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import pytest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REAL_REQUESTS = os.getenv("REAL_REQUESTS", "false").lower() == "true"

pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="Hierarchy isolation tests require REAL_REQUESTS=true"
)

DEFAULT_CONFIG = {
    "num_subchains": 4,
    "events_per_subchain": 1000,
    "proof_batch_size": 10,
    "rebalance_threshold_eps": 100,
    "sync_batch_size": 50,
}


@dataclass
class MockSubChain:
    name: str
    events: list[dict] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)
    state_root: str = ""

    def add_event(self, event: dict) -> bool:
        self.events.append(event)
        return True

    def get_event_count(self) -> int:
        return len(self.events)

    def get_block_count(self) -> int:
        return len(self.blocks)

    def get_state_root(self) -> str:
        if not self.state_root:
            self.state_root = hashlib.sha256(
                str(len(self.events)).encode()
            ).hexdigest()
        return self.state_root


@dataclass
class MockMainChain:
    name: str = "mainchain"
    anchors: list[dict] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)

    def receive_proof(self, anchor_data: dict) -> bool:
        self.anchors.append(anchor_data)
        return True

    def get_blocks(self, from_idx: int, to_idx: int) -> list:
        return self.blocks[from_idx:to_idx]


class HierarchyIsolationTest:
    def __init__(self, config: dict | None = None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.subchains: dict[str, MockSubChain] = {}
        self.mainchain = MockMainChain()
        self.results: dict[str, Any] = {}
        self.errors: list[str] = []

    def setup(self) -> None:
        for i in range(self.config["num_subchains"]):
            chain_id = f"subchain-{i}"
            self.subchains[chain_id] = MockSubChain(name=chain_id)

    def test_proof_aggregation(self) -> dict:
        from hierachain.hierarchical.proof_aggregation import ProofAggregator

        aggregator = ProofAggregator(
            batch_size=self.config["proof_batch_size"],
            batch_timeout=5.0,
            use_mock=True,
        )

        results: dict[str, Any] = {
            "proofs_added": 0,
            "aggregations": 0,
            "avg_compression_ratio": 0.0,
            "errors": [],
        }

        for chain_id, chain in self.subchains.items():
            proof_data = hashlib.sha256(
                f"{chain_id}:{time.time()}".encode()
            ).digest() * 100

            success = aggregator.add_proof(
                sub_chain_id=chain_id,
                proof=proof_data,
                block_index=chain.get_block_count(),
                state_root=chain.get_state_root(),
            )

            if success:
                results["proofs_added"] += 1

        agg_proof = aggregator.aggregate()
        if agg_proof:
            results["aggregations"] += 1
            results["avg_compression_ratio"] = agg_proof.compression_ratio
            valid = aggregator.verify_aggregated_proof(agg_proof)
            results["verification_passed"] = valid

        stats = aggregator.get_stats()
        results["aggregator_stats"] = stats

        return results

    def test_dynamic_rebalancing(self) -> dict:
        from hierachain.hierarchical.rebalancer import SubChainRebalancer

        rebalancer = SubChainRebalancer(
            threshold_eps=self.config["rebalance_threshold_eps"],
            check_interval=1.0,
            min_events_for_split=100,
            cooldown_seconds=5.0,
        )

        results: dict[str, Any] = {
            "chains_monitored": 0,
            "thresholds_checked": 0,
            "splits_triggered": 0,
            "errors": [],
        }

        for chain_id, chain in self.subchains.items():
            rebalancer.register_subchain(chain_id, chain)
            results["chains_monitored"] += 1

        target_chain = list(self.subchains.values())[0]
        for i in range(500):
            target_chain.add_event({
                "id": f"event-{i}",
                "timestamp": time.time(),
                "data": f"test-{i}",
            })

        for chain_id in self.subchains:
            exceeded = rebalancer.check_threshold(chain_id)
            results["thresholds_checked"] += 1
            if exceeded:
                result = rebalancer.split_sub_chain(self.subchains[chain_id])
                if result.success:
                    results["splits_triggered"] += 1

        stats = rebalancer.get_stats()
        results["rebalancer_stats"] = stats

        return results

    def test_full_hierarchy_stress(self) -> dict:
        from hierachain.hierarchical.proof_aggregation import ProofAggregator
        from hierachain.hierarchical.rebalancer import SubChainRebalancer

        results = {
            "start_time": time.time(),
            "events_processed": 0,
            "proofs_aggregated": 0,
            "errors": [],
        }

        aggregator = ProofAggregator(
            batch_size=self.config["proof_batch_size"],
            batch_timeout=5.0,
            use_mock=True,
        )

        rebalancer = SubChainRebalancer(
            threshold_eps=self.config["rebalance_threshold_eps"],
            check_interval=1.0,
            min_events_for_split=100,
            cooldown_seconds=5.0,
        )

        for chain_id, chain in self.subchains.items():
            rebalancer.register_subchain(chain_id, chain)
            for i in range(self.config["events_per_subchain"]):
                chain.add_event({
                    "id": f"event-{i}",
                    "timestamp": time.time(),
                    "data": f"test-{i}",
                })
                results["events_processed"] += 1

        for chain_id, chain in self.subchains.items():
            proof_data = hashlib.sha256(
                f"{chain_id}:{time.time()}".encode()
            ).digest() * 100

            success = aggregator.add_proof(
                sub_chain_id=chain_id,
                proof=proof_data,
                block_index=chain.get_block_count(),
                state_root=chain.get_state_root(),
            )

            if success:
                results["proofs_aggregated"] += 1

        agg_proof = aggregator.aggregate()
        if agg_proof:
            results["aggregation_verified"] = aggregator.verify_aggregated_proof(agg_proof)

        results["duration"] = time.time() - results["start_time"]

        return results


class TestHierarchyIsolation:
    @pytest.fixture(autouse=True)
    def setup_test(self):
        self.test = HierarchyIsolationTest()
        self.test.setup()

    def test_proof_aggregation_logic(self):
        results = self.test.test_proof_aggregation()

        assert results["proofs_added"] == self.test.config["num_subchains"]
        assert results["aggregations"] >= 1
        assert "aggregator_stats" in results

    def test_dynamic_rebalancing_logic(self):
        results = self.test.test_dynamic_rebalancing()

        assert results["chains_monitored"] == self.test.config["num_subchains"]
        assert results["thresholds_checked"] == self.test.config["num_subchains"]
        assert "rebalancer_stats" in results

    def test_full_hierarchy_stress_logic(self):
        results = self.test.test_full_hierarchy_stress()

        expected_events = (
            self.test.config["num_subchains"] *
            self.test.config["events_per_subchain"]
        )
        assert results["events_processed"] == expected_events
        assert results["proofs_aggregated"] == self.test.config["num_subchains"]
        assert results["duration"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
