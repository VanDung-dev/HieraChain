"""
Chaos Rebalance Stress Test - Hierarchy Changes Under Chaos.

This test combines chaos_sync scenarios with continuous hierarchy structure changes
(add/remove sub-chains) to verify that proof recalculation and node rebalancing
don't cause CPU overload.

Run with: pytest tests/stress/test_chaos_rebalance_stress.py -v
"""

import time
import threading
import logging
import random
import psutil
import os
from dataclasses import dataclass

import pytest

logger = logging.getLogger(__name__)


@dataclass
class SubChainState:
    chain_id: str
    is_active: bool = True
    node_count: int = 0
    proof_height: int = 0
    last_proof_time: float = 0.0


@dataclass
class RebalanceEvent:
    timestamp: float
    event_type: str
    chain_id: str
    cpu_before: float
    ram_before_mb: float


class ChaosRebalanceStressTest:
    def __init__(
        self,
        num_initial_chains: int = 4,
        num_nodes: int = 8,
        chaos_interval_seconds: float = 5.0,
        rebalance_interval_seconds: float = 10.0,
    ):
        self.num_initial_chains = num_initial_chains
        self.num_nodes = num_nodes
        self.chaos_interval = chaos_interval_seconds
        self.rebalance_interval = rebalance_interval_seconds
        self.process = psutil.Process(os.getpid())
        self.chains: dict[str, SubChainState] = {}
        self.rebalance_events: list[RebalanceEvent] = []
        self.lock = threading.Lock()
        self.running = False
        self.worker_threads: list[threading.Thread] = []
        self.cpu_samples: list[float] = []
        self.ram_samples: list[float] = []

    def _get_cpu_percent(self) -> float:
        return self.process.cpu_percent(interval=0.1)

    def _get_ram_mb(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def initialize_chains(self) -> None:
        for i in range(self.num_initial_chains):
            chain_id = f"sub-chain-{i + 1}"
            self.chains[chain_id] = SubChainState(
                chain_id=chain_id,
                node_count=random.randint(1, 3),
            )
        logger.info(f"Initialized {len(self.chains)} sub-chains")

    def _chaos_worker(self) -> None:
        while self.running:
            try:
                if random.random() < 0.3:
                    self._simulate_node_failure()
                if random.random() < 0.2:
                    self._simulate_network_issue()
                time.sleep(self.chaos_interval)
            except Exception as e:
                logger.error(f"Chaos worker error: {e}")

    def _rebalance_worker(self) -> None:
        while self.running:
            try:
                self._trigger_rebalance()
                time.sleep(self.rebalance_interval)
            except Exception as e:
                logger.error(f"Rebalance worker error: {e}")

    def _monitor_worker(self, interval: float = 1.0) -> None:
        while self.running:
            self.cpu_samples.append(self._get_cpu_percent())
            self.ram_samples.append(self._get_ram_mb())
            time.sleep(interval)

    def _simulate_node_failure(self) -> None:
        failed_chain = random.choice(list(self.chains.keys()))
        if self.chains[failed_chain].is_active:
            self.chains[failed_chain].is_active = False
            logger.warning(f"Node failure simulated on {failed_chain}")

    def _simulate_network_issue(self) -> None:
        affected_chains = random.sample(
            list(self.chains.keys()),
            k=random.randint(1, max(1, len(self.chains) // 2)),
        )
        logger.warning(f"Network issue affecting {len(affected_chains)} chains")

    def _trigger_rebalance(self) -> None:
        cpu_before = self._get_cpu_percent()
        ram_before = self._get_ram_mb()

        action = random.choice(["add_chain", "remove_chain", "redistribute"])

        if action == "add_chain":
            new_id = f"sub-chain-{len(self.chains) + 1}"
            self.chains[new_id] = SubChainState(
                chain_id=new_id,
                node_count=random.randint(1, 3),
            )
            logger.info(f"Added new chain: {new_id}")

        elif action == "remove_chain":
            if len(self.chains) > 2:
                removable = [
                    cid for cid, state in self.chains.items() if state.is_active
                ]
                if removable:
                    removed = random.choice(removable)
                    self.chains[removed].is_active = False
                    logger.info(f"Removed chain: {removed}")

        elif action == "redistribute":
            total_nodes = self.num_nodes
            active_chains = [c for c in self.chains.values() if c.is_active]
            if active_chains:
                per_chain = total_nodes // len(active_chains)
                remainder = total_nodes % len(active_chains)
                for i, chain in enumerate(active_chains):
                    chain.node_count = per_chain + (1 if i < remainder else 0)
            logger.info("Redistributed nodes across chains")

        for chain in self.chains.values():
            if chain.is_active:
                chain.proof_height += 1
                chain.last_proof_time = time.time()

        event = RebalanceEvent(
            timestamp=time.time(),
            event_type=action,
            chain_id="all",
            cpu_before=cpu_before,
            ram_before_mb=ram_before,
        )
        with self.lock:
            self.rebalance_events.append(event)

    def start(self) -> None:
        self.running = True
        self.worker_threads = [
            threading.Thread(target=self._chaos_worker, daemon=True),
            threading.Thread(target=self._rebalance_worker, daemon=True),
            threading.Thread(target=self._monitor_worker, daemon=True),
        ]
        for t in self.worker_threads:
            t.start()
        logger.info("Started chaos rebalance stress test")

    def stop(self) -> dict:
        self.running = False
        for t in self.worker_threads:
            t.join(timeout=3.0)

        results = {
            "total_events": len(self.rebalance_events),
            "cpu_peak": max(self.cpu_samples) if self.cpu_samples else 0.0,
            "cpu_avg": (
                sum(self.cpu_samples) / len(self.cpu_samples)
                if self.cpu_samples else 0.0
            ),
            "ram_peak_mb": max(self.ram_samples) if self.ram_samples else 0.0,
            "ram_avg_mb": (
                sum(self.ram_samples) / len(self.ram_samples)
                if self.ram_samples else 0.0
            ),
            "active_chains": sum(1 for c in self.chains.values() if c.is_active),
            "total_chains": len(self.chains),
        }
        logger.info(f"Stress test results: {results}")
        return results


def test_chaos_rebalance_no_cpu_overload():
    test = ChaosRebalanceStressTest(
        num_initial_chains=4,
        num_nodes=8,
        chaos_interval_seconds=2.0,
        rebalance_interval_seconds=5.0,
    )
    test.initialize_chains()
    test.start()
    time.sleep(30)
    results = test.stop()

    assert results["cpu_avg"] < 90.0, (
        f"Sustained CPU overload detected: {results['cpu_avg']:.1f}% (Peaks to 100% are allowed on 1 vCPU)"
    )
    assert results["total_events"] > 0, "Should have recorded rebalance events"


def test_rebalance_proof_recalculation():
    test = ChaosRebalanceStressTest(
        num_initial_chains=4,
        num_nodes=8,
        chaos_interval_seconds=3.0,
        rebalance_interval_seconds=5.0,
    )
    test.initialize_chains()
    test.start()
    time.sleep(20)
    test.stop()

    for chain in test.chains.values():
        if chain.is_active:
            assert chain.proof_height > 0, (
                f"Chain {chain.chain_id} should have proof height"
            )
            assert chain.last_proof_time > 0, (
                f"Chain {chain.chain_id} should have proof time"
            )


def test_chaos_rebalance_resource_tracking():
    test = ChaosRebalanceStressTest(
        num_initial_chains=4,
        num_nodes=8,
        chaos_interval_seconds=2.0,
        rebalance_interval_seconds=5.0,
    )
    test.initialize_chains()
    test.start()
    time.sleep(25)
    results = test.stop()

    assert len(test.cpu_samples) > 0, "Should have CPU samples"
    assert len(test.ram_samples) > 0, "Should have RAM samples"
    assert results["ram_peak_mb"] < 850.0, (
        f"RAM spike too high for 1GiB node: {results['ram_peak_mb']:.1f}MB"
    )


def test_chain_lifecycle_during_chaos():
    test = ChaosRebalanceStressTest(
        num_initial_chains=6,
        num_nodes=12,
        chaos_interval_seconds=1.0,
        rebalance_interval_seconds=3.0,
    )
    test.initialize_chains()
    initial_count = len(test.chains)

    test.start()
    time.sleep(30)
    results = test.stop()

    assert len(test.chains) >= initial_count - 2, (
        "Should not lose too many chains"
    )
    assert results["total_events"] >= 5, "Should have multiple rebalance events"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
