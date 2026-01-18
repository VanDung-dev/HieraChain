"""
Stress Tests for Hierarchical Tree Logic.

This module contains comprehensive stress tests for:
- K8s namespace isolation
- Cross-level state sync
- Proof aggregation under load
- Dynamic sub-chain rebalancing

Test environment: Docker + Kubernetes
"""

import hashlib
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

import pytest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default test configuration
DEFAULT_CONFIG = {
    "num_subchains": 4,
    "events_per_subchain": 1000,
    "test_duration_seconds": 60,
    "proof_batch_size": 10,
    "rebalance_threshold_eps": 100,
    "sync_batch_size": 50,
}


@dataclass
class MockSubChain:
    """Mock sub-chain for testing."""
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
    """Mock main chain for testing."""
    name: str = "mainchain"
    anchors: list[dict] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)
    
    def receive_proof(self, anchor_data: dict) -> bool:
        self.anchors.append(anchor_data)
        return True
    
    def add_event(self, event: dict) -> bool:
        return True
    
    def get_blocks(self, from_idx: int, to_idx: int) -> list:
        return self.blocks[from_idx:to_idx]


class HierarchyIsolationTest:
    """Stress test for hierarchical features."""
    
    def __init__(self, config: dict | None = None):
        self.config = config or DEFAULT_CONFIG.copy()
        
        # Determine strict mock mode from environment
        # Default to True (Safe) unless explicitly set to "true"
        self.use_mock = os.getenv("REAL_REQUESTS", "false").lower() != "true"
        if not self.use_mock:
            logger.warning("⚠️ RUNNING IN REAL MODE: Operations will affect connected K8s cluster!")
            
        self.subchains: dict[str, MockSubChain] = {}
        self.mainchain = MockMainChain()
        self.results: dict[str, Any] = {}
        self.errors: list[str] = []
    
    def setup(self) -> None:
        """Initialize test components."""
        for i in range(self.config["num_subchains"]):
            chain_id = f"subchain-{i}"
            self.subchains[chain_id] = MockSubChain(name=chain_id)
    
    def test_k8s_namespace_isolation(self) -> dict:
        """Test K8s namespace isolation for sub-chains."""
        from hierachain.hierarchical.k8s_namespace_manager import (
            K8sNamespaceManager,
            NamespaceStatus,
        )
        
        manager = K8sNamespaceManager(use_mock=self.use_mock)
        results = {
            "namespaces_created": 0,
            "namespaces_deleted": 0,
            "status_checks": 0,
            "errors": [],
        }
        
        # Create namespaces for each subchain
        for chain_id in self.subchains:
            success = manager.create_namespace(chain_id)
            if success:
                results["namespaces_created"] += 1
            else:
                results["errors"].append(f"Failed to create {chain_id}")
        
        # Check statuses
        for chain_id in self.subchains:
            status = manager.get_namespace_status(chain_id)
            if status == NamespaceStatus.ACTIVE:
                results["status_checks"] += 1
        
        # Delete namespaces
        for chain_id in self.subchains:
            success = manager.delete_namespace(chain_id)
            if success:
                results["namespaces_deleted"] += 1
        
        stats = manager.get_stats()
        results["manager_stats"] = stats
        
        return results
    
    def test_proof_aggregation(self) -> dict:
        """Test proof aggregation under load."""
        from hierachain.hierarchical.proof_aggregation import ProofAggregator
        
        aggregator = ProofAggregator(
            batch_size=self.config["proof_batch_size"],
            batch_timeout=5.0,
            use_mock=self.use_mock,
        )
        
        results = {
            "proofs_added": 0,
            "aggregations": 0,
            "avg_compression_ratio": 0.0,
            "errors": [],
        }
        
        # Add proofs from each subchain
        for chain_id, chain in self.subchains.items():
            # Generate mock proof
            proof_data = hashlib.sha256(
                f"{chain_id}:{time.time()}".encode()
            ).digest() * 100  # ~3.2KB proof
            
            success = aggregator.add_proof(
                sub_chain_id=chain_id,
                proof=proof_data,
                block_index=chain.get_block_count(),
                state_root=chain.get_state_root(),
            )
            
            if success:
                results["proofs_added"] += 1
        
        # Force aggregation
        agg_proof = aggregator.aggregate()
        if agg_proof:
            results["aggregations"] += 1
            results["avg_compression_ratio"] = agg_proof.compression_ratio
        
        # Verify aggregated proof
        if agg_proof:
            valid = aggregator.verify_aggregated_proof(agg_proof)
            results["verification_passed"] = valid
        
        stats = aggregator.get_stats()
        results["aggregator_stats"] = stats
        
        return results
    
    def test_cross_level_sync(self) -> dict:
        """Test cross-level state synchronization."""
        from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
        
        sync_manager = CrossLevelSyncManager(
            node_id="test-node",
            batch_size=self.config["sync_batch_size"],
        )
        
        results = {
            "syncs_down": 0,
            "syncs_up": 0,
            "conflicts": 0,
            "errors": [],
        }
        
        # Connect chains
        sync_manager.connect_mainchain(self.mainchain)
        for chain_id, chain in self.subchains.items():
            sync_manager.connect_subchain(chain_id, chain)
        
        # Test sync down (MainChain -> SubChain)
        for chain_id in self.subchains:
            result = sync_manager.sync_from_mainchain(chain_id)
            if result.success:
                results["syncs_down"] += 1
        
        # Test sync up (SubChain -> MainChain)
        for chain_id, chain in self.subchains.items():
            proof = hashlib.sha256(chain.get_state_root().encode()).digest()
            result = sync_manager.sync_to_mainchain(chain_id, proof)
            if result.success:
                results["syncs_up"] += 1
        
        stats = sync_manager.get_stats()
        results["sync_stats"] = stats
        
        return results
    
    def test_dynamic_rebalancing(self) -> dict:
        """Test dynamic sub-chain rebalancing."""
        from hierachain.hierarchical.rebalancer import SubChainRebalancer
        
        rebalancer = SubChainRebalancer(
            threshold_eps=self.config["rebalance_threshold_eps"],
            check_interval=1.0,
            min_events_for_split=100,
            cooldown_seconds=5.0,
        )
        
        results = {
            "chains_monitored": 0,
            "thresholds_checked": 0,
            "splits_triggered": 0,
            "errors": [],
        }
        
        # Register subchains
        for chain_id, chain in self.subchains.items():
            rebalancer.register_subchain(chain_id, chain)
            results["chains_monitored"] += 1
        
        # Add events to trigger threshold
        target_chain = list(self.subchains.values())[0]
        for i in range(500):
            target_chain.add_event({
                "id": f"event-{i}",
                "timestamp": time.time(),
                "data": f"test-{i}",
            })
        
        # Check threshold
        for chain_id in self.subchains:
            exceeded = rebalancer.check_threshold(chain_id)
            results["thresholds_checked"] += 1
            if exceeded:
                result = rebalancer.split_sub_chain(
                    self.subchains[chain_id]
                )
                if result.success:
                    results["splits_triggered"] += 1
        
        stats = rebalancer.get_stats()
        results["rebalancer_stats"] = stats
        
        return results
    
    def test_full_hierarchy_stress(self) -> dict:
        """Full stress test combining all hierarchy features."""
        from hierachain.hierarchical.k8s_namespace_manager import (
            K8sNamespaceManager,
        )
        from hierachain.hierarchical.proof_aggregation import ProofAggregator
        from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
        from hierachain.hierarchical.rebalancer import SubChainRebalancer
        
        results = {
            "start_time": time.time(),
            "events_processed": 0,
            "proofs_aggregated": 0,
            "syncs_completed": 0,
            "errors": [],
        }
        
        # Initialize components
        k8s_mgr = K8sNamespaceManager(use_mock=self.use_mock)
        aggregator = ProofAggregator(batch_size=5, use_mock=self.use_mock)
        sync_mgr = CrossLevelSyncManager(node_id="stress-test")
        rebalancer = SubChainRebalancer(
            threshold_eps=200,
            min_events_for_split=200,
        )
        
        sync_mgr.connect_mainchain(self.mainchain)
        
        # Setup namespaces and chains
        for chain_id, chain in self.subchains.items():
            k8s_mgr.create_namespace(chain_id)
            sync_mgr.connect_subchain(chain_id, chain)
            rebalancer.register_subchain(chain_id, chain)
        
        # Process events
        duration = self.config["test_duration_seconds"]
        end_time = time.time() + min(duration, 10)  # Cap at 10s for CI
        
        while time.time() < end_time:
            # Add events to random subchain
            chain_id = random.choice(list(self.subchains.keys()))
            chain = self.subchains[chain_id]
            
            chain.add_event({
                "id": f"stress-{results['events_processed']}",
                "timestamp": time.time(),
                "chain": chain_id,
            })
            results["events_processed"] += 1
            
            # Periodically aggregate proofs
            if results["events_processed"] % 10 == 0:
                proof = hashlib.sha256(
                    chain.get_state_root().encode()
                ).digest()
                aggregator.add_proof(
                    sub_chain_id=chain_id,
                    proof=proof,
                    block_index=chain.get_block_count(),
                    state_root=chain.get_state_root(),
                )
            
            # Periodically sync
            if results["events_processed"] % 50 == 0:
                sync_result = sync_mgr.sync_to_mainchain(chain_id)
                if sync_result.success:
                    results["syncs_completed"] += 1
        
        # Force final aggregation
        agg = aggregator.aggregate()
        if agg:
            results["proofs_aggregated"] = len(agg.source_proofs)
        
        results["duration_seconds"] = time.time() - results["start_time"]
        results["events_per_second"] = (
            results["events_processed"] / results["duration_seconds"]
        )
        
        return results
    
    def run_all_tests(self) -> dict:
        """Run all hierarchy stress tests."""
        self.setup()
        
        all_results = {
            "start_time": time.time(),
            "tests": {},
            "errors": [],
            # Subchain metrics
            "subchain_metrics": {
                "num_subchains": self.config["num_subchains"],
                "events_per_subchain": self.config["events_per_subchain"],
                "proof_batch_size": self.config["proof_batch_size"],
                "rebalance_threshold_eps": self.config["rebalance_threshold_eps"],
                "sync_batch_size": self.config["sync_batch_size"],
            },
        }
        
        tests = [
            ("k8s_namespace_isolation", self.test_k8s_namespace_isolation),
            ("proof_aggregation", self.test_proof_aggregation),
            ("cross_level_sync", self.test_cross_level_sync),
            ("dynamic_rebalancing", self.test_dynamic_rebalancing),
            ("full_hierarchy_stress", self.test_full_hierarchy_stress),
        ]
        
        for name, test_fn in tests:
            logger.info(f"Running test: {name}")
            try:
                result = test_fn()
                all_results["tests"][name] = {
                    "status": "passed",
                    "result": result,
                }
            except Exception as e:
                logger.error(f"Test {name} failed: {e}")
                all_results["tests"][name] = {
                    "status": "failed",
                    "error": str(e),
                }
                all_results["errors"].append(f"{name}: {e}")
        
        all_results["duration_seconds"] = (
            time.time() - all_results["start_time"]
        )
        all_results["tests_passed"] = sum(
            1 for t in all_results["tests"].values() if t["status"] == "passed"
        )
        all_results["tests_failed"] = len(all_results["errors"])
        
        # Calculate total events processed across all subchains
        total_events = sum(
            chain.get_event_count() for chain in self.subchains.values()
        )
        all_results["subchain_metrics"]["total_events_processed"] = total_events
        all_results["subchain_metrics"]["avg_events_per_subchain"] = (
            total_events / len(self.subchains) if self.subchains else 0
        )
        
        return all_results


# Pytest test cases


class TestHierarchyIsolation:
    """Pytest test cases for hierarchy isolation."""
    
    @pytest.fixture
    def quick_config(self):
        """Quick config for fast tests."""
        return {
            "num_subchains": 2,
            "events_per_subchain": 100,
            "test_duration_seconds": 5,
            "proof_batch_size": 5,
            "rebalance_threshold_eps": 50,
            "sync_batch_size": 20,
        }
    
    def test_k8s_namespace_manager(self):
        """Test K8s namespace manager creation and lifecycle."""
        from hierachain.hierarchical.k8s_namespace_manager import (
            K8sNamespaceManager,
            NamespaceStatus,
        )
        
        manager = K8sNamespaceManager(use_mock=True)
        
        # Create namespace
        success = manager.create_namespace("test-chain")
        assert success
        
        # Check status
        status = manager.get_namespace_status("test-chain")
        assert status == NamespaceStatus.ACTIVE
        
        # Delete namespace
        success = manager.delete_namespace("test-chain")
        assert success
    
    def test_proof_aggregator(self):
        """Test proof aggregation."""
        from hierachain.hierarchical.proof_aggregation import (
            ProofAggregator,
            AggregationStatus,
        )
        
        aggregator = ProofAggregator(batch_size=3, use_mock=True)
        
        # Add proofs - when we hit batch_size, auto-aggregation triggers
        for i in range(3):
            proof = hashlib.sha256(f"proof-{i}".encode()).digest()
            aggregator.add_proof(
                sub_chain_id=f"chain-{i}",
                proof=proof,
                block_index=i,
                state_root=hashlib.sha256(f"state-{i}".encode()).hexdigest(),
            )
        
        # After adding exactly batch_size proofs, aggregation should have triggered
        # Get the latest aggregation result
        agg = aggregator.get_latest_aggregation()
        assert agg is not None, "Aggregation should have been triggered"
        assert len(agg.source_proofs) == 3
    
    def test_cross_level_sync_manager(self):
        """Test cross-level sync manager."""
        from hierachain.cluster.cross_level_sync import (
            CrossLevelSyncManager,
            CrossLevelSyncStatus,
        )
        
        manager = CrossLevelSyncManager(node_id="test")
        mainchain = MockMainChain()
        subchain = MockSubChain(name="test-sub")
        
        manager.connect_mainchain(mainchain)
        manager.connect_subchain("test-sub", subchain)
        
        # Test sync
        result = manager.sync_to_mainchain("test-sub")
        assert result.success
    
    def test_rebalancer(self):
        """Test sub-chain rebalancer."""
        from hierachain.hierarchical.rebalancer import (
            SubChainRebalancer,
            RebalanceStatus,
        )
        
        rebalancer = SubChainRebalancer(
            threshold_eps=10,
            min_events_for_split=50,
        )
        
        chain = MockSubChain(name="test-chain")
        rebalancer.register_subchain("test-chain", chain)
        
        # Add events below threshold
        for i in range(30):
            chain.add_event({"id": i})
        
        # Should not trigger split
        assert not rebalancer.check_threshold("test-chain")
    
    def test_quick_stress(self, quick_config):
        """Quick stress test."""
        test = HierarchyIsolationTest(quick_config)
        test.setup()
        
        # Run individual quick tests
        k8s_result = test.test_k8s_namespace_isolation()
        assert k8s_result["namespaces_created"] == quick_config["num_subchains"]
        
        proof_result = test.test_proof_aggregation()
        assert proof_result["proofs_added"] == quick_config["num_subchains"]
    
    @pytest.mark.slow
    def test_full_stress(self):
        """Full stress test (marked as slow)."""
        config = {
            "num_subchains": 4,
            "events_per_subchain": 200,
            "test_duration_seconds": 15,
            "proof_batch_size": 10,
            "rebalance_threshold_eps": 100,
            "sync_batch_size": 50,
        }
        
        test = HierarchyIsolationTest(config)
        results = test.run_all_tests()
        
        # --- PRINT METRICS FOR PYTEST REPORT ---
        print("\n" + "=" * 60)
        print("  SUBCHAIN CONFIGURATION (Captured in Report)")
        print("=" * 60)
        metrics = results.get("subchain_metrics", {})
        if metrics:
            print(f"  📦 Number of Subchains:        {metrics.get('num_subchains')}")
            print(f"  📝 Events per Subchain:        {metrics.get('events_per_subchain')}")
            print(f"  📊 Total Events Processed:     {metrics.get('total_events_processed')}")
            print(f"  📈 Avg Events per Subchain:    {metrics.get('avg_events_per_subchain', 0):.2f}")
            print(f"  🔗 Proof Batch Size:           {metrics.get('proof_batch_size')}")
            print(f"  ⚡ Rebalance Threshold (EPS):  {metrics.get('rebalance_threshold_eps')}")
            print(f"  🔄 Sync Batch Size:            {metrics.get('sync_batch_size')}")

        print("\n" + "=" * 60)
        print("  PERFORMANCE SUMMARY")
        print("=" * 60)
        if "full_hierarchy_stress" in results["tests"]:
            stress_result = results["tests"]["full_hierarchy_stress"]
            if stress_result["status"] == "passed":
                r = stress_result["result"]
                print(f"  🚀 Events/Second:     {r.get('events_per_second', 0):.2f}")
                print(f"  🔗 Proofs Aggregated: {r.get('proofs_aggregated', 0)}")
                print(f"  🔄 Syncs Completed:   {r.get('syncs_completed', 0)}")
        print("=" * 60)
        # ---------------------------------------

        assert results["tests_failed"] == 0
        assert results["tests_passed"] >= 4


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("  HIERARCHY ISOLATION STRESS TESTS")
    print("  Related to: TODO Item 7 - Hierarchical Tree Logic")
    print("=" * 60)
    print()
    
    test = HierarchyIsolationTest()
    results = test.run_all_tests()
    
    # Display subchain metrics prominently
    print("\n" + "=" * 60)
    print("  SUBCHAIN CONFIGURATION")
    print("=" * 60)
    metrics = results["subchain_metrics"]
    print(f"  📦 Number of Subchains:        {metrics['num_subchains']}")
    print(f"  📝 Events per Subchain:        {metrics['events_per_subchain']}")
    print(f"  📊 Total Events Processed:     {metrics['total_events_processed']}")
    print(f"  📈 Avg Events per Subchain:    {metrics['avg_events_per_subchain']:.2f}")
    print(f"  🔗 Proof Batch Size:           {metrics['proof_batch_size']}")
    print(f"  ⚡ Rebalance Threshold (EPS):  {metrics['rebalance_threshold_eps']}")
    print(f"  🔄 Sync Batch Size:            {metrics['sync_batch_size']}")
    
    # Display test results
    print("\n" + "=" * 60)
    print("  TEST RESULTS")
    print("=" * 60)
    print(f"  ⏱️  Duration: {results['duration_seconds']:.2f}s")
    print(f"  ✅ Passed: {results['tests_passed']}")
    print(f"  ❌ Failed: {results['tests_failed']}")
    
    for name, result in results["tests"].items():
        status_emoji = "✅" if result["status"] == "passed" else "❌"
        print(f"\n{status_emoji} {name}")
        if result["status"] == "passed":
            for key, value in result["result"].items():
                if not isinstance(value, dict):
                    print(f"    {key}: {value}")
        else:
            print(f"    Error: {result.get('error', 'Unknown')}")
    
    # Performance summary
    print("\n" + "=" * 60)
    print("  PERFORMANCE SUMMARY")
    print("=" * 60)
    if "full_hierarchy_stress" in results["tests"]:
        stress_result = results["tests"]["full_hierarchy_stress"]
        if stress_result["status"] == "passed":
            r = stress_result["result"]
            print(f"  🚀 Events/Second:     {r.get('events_per_second', 0):.2f}")
            print(f"  🔗 Proofs Aggregated: {r.get('proofs_aggregated', 0)}")
            print(f"  🔄 Syncs Completed:   {r.get('syncs_completed', 0)}")
    print("=" * 60)
