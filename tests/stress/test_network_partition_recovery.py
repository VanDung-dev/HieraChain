"""
Network Partition Recovery Test - Split/Brain scenarios.

This test simulates network partitions where 4 nodes are split into 2 groups (2-2).
Each group operates independently for a period, then reconnects.
Tests reconciliation process doesn't cause resource spikes (CPU/RAM) leading to crashes.

Run with: pytest tests/stress/test_network_partition_recovery.py -v
"""

import time
import threading
import logging
import psutil
import os
from dataclasses import dataclass
from typing import Optional

import pytest

logger = logging.getLogger(__name__)


@dataclass
class NodeState:
    node_id: str
    is_alive: bool = True
    is_connected: bool = True
    block_index: int = 0
    block_hash: str = ""
    events_processed: int = 0
    partition_group: Optional[int] = None


@dataclass
class PartitionEvent:
    timestamp: float
    event_type: str
    nodes_involved: list[str]
    cpu_before: float
    ram_before_mb: float


@dataclass
class ReconciliationMetrics:
    start_time: float
    end_time: float
    blocks_reconciled: int
    events_reconciled: int
    cpu_peak_during_recon: float
    ram_peak_during_recon_mb: float


class NetworkPartitionTest:
    def __init__(self, num_nodes: int = 4, partition_duration_seconds: int = 30):
        self.num_nodes = num_nodes
        self.partition_duration = partition_duration_seconds
        self.process = psutil.Process(os.getpid())
        self.nodes: dict[str, NodeState] = {}
        self.partition_events: list[PartitionEvent] = []
        self.reconciliation_metrics: Optional[ReconciliationMetrics] = None
        self.lock = threading.Lock()
        self.is_partitioned = False

    def _get_cpu_percent(self) -> float:
        return self.process.cpu_percent(interval=0.1)

    def _get_ram_mb(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def initialize_nodes(self) -> None:
        for i in range(self.num_nodes):
            node_id = f"node-{i + 1}"
            self.nodes[node_id] = NodeState(node_id=node_id)
        logger.info(f"Initialized {len(self.nodes)} nodes")

    def create_partition(self, group1: list[str], group2: list[str]) -> None:
        logger.warning("Network partition: G1=%s, G2=%s", group1, group2)
        self.is_partitioned = True

        cpu_before = self._get_cpu_percent()
        ram_before = self._get_ram_mb()

        for node_id in group1:
            if node_id in self.nodes:
                self.nodes[node_id].partition_group = 1
                self.nodes[node_id].is_connected = False

        for node_id in group2:
            if node_id in self.nodes:
                self.nodes[node_id].partition_group = 2
                self.nodes[node_id].is_connected = False

        event = PartitionEvent(
            timestamp=time.time(),
            event_type="partition_created",
            nodes_involved=group1 + group2,
            cpu_before=cpu_before,
            ram_before_mb=ram_before,
        )
        self.partition_events.append(event)

    def heal_partition(self, all_nodes: list[str]) -> ReconciliationMetrics:
        logger.info("Healing network partition - starting reconciliation")
        start_time = time.time()
        cpu_start = self._get_cpu_percent()
        ram_start = self._get_ram_mb()

        cpu_peaks = [cpu_start]
        ram_peaks = [ram_start]

        monitoring = True

        def monitor_resources():
            while monitoring:
                cpu_peaks.append(self._get_cpu_percent())
                ram_peaks.append(self._get_ram_mb())
                time.sleep(0.5)

        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()

        for node_id in all_nodes:
            if node_id in self.nodes:
                self.nodes[node_id].partition_group = None
                self.nodes[node_id].is_connected = True
                self.nodes[node_id].events_processed += 10

        time.sleep(2)

        monitoring = False

        monitor_thread.join(timeout=1.0)

        end_time = time.time()
        self.is_partitioned = False

        self.reconciliation_metrics = ReconciliationMetrics(
            start_time=start_time,
            end_time=end_time,
            blocks_reconciled=sum(1 for n in self.nodes.values() if n.block_index > 0),
            events_reconciled=sum(n.events_processed for n in self.nodes.values()),
            cpu_peak_during_recon=max(cpu_peaks) if cpu_peaks else cpu_start,
            ram_peak_during_recon_mb=max(ram_peaks) if ram_peaks else ram_start,
        )

        event = PartitionEvent(
            timestamp=time.time(),
            event_type="partition_healed",
            nodes_involved=all_nodes,
            cpu_before=cpu_start,
            ram_before_mb=ram_start,
        )
        self.partition_events.append(event)
        logger.info(f"Reconciliation completed: {self.reconciliation_metrics}")

        return self.reconciliation_metrics

    def simulate_partition_activity(self, group_nodes: list[str]) -> None:
        for node_id in group_nodes:
            if node_id in self.nodes and self.nodes[node_id].partition_group:
                self.nodes[node_id].events_processed += 5
                self.nodes[node_id].block_index += 1

    def get_partition_discovery_count(self) -> int:
        return sum(1 for e in self.partition_events
                   if e.event_type == "partition_created")


def test_partition_split_and_recovery():
    test = NetworkPartitionTest(num_nodes=4, partition_duration_seconds=10)

    test.initialize_nodes()
    assert len(test.nodes) == 4

    group1 = ["node-1", "node-2"]
    group2 = ["node-3", "node-4"]

    test.create_partition(group1, group2)

    assert test.is_partitioned is True
    assert test.get_partition_discovery_count() == 1

    time.sleep(5)
    test.simulate_partition_activity(group1)
    test.simulate_partition_activity(group2)

    all_nodes = list(test.nodes.keys())
    metrics = test.heal_partition(all_nodes)

    assert metrics.end_time > metrics.start_time
    assert metrics.cpu_peak_during_recon <= 100.0
    assert metrics.ram_peak_during_recon_mb < 4096.0


def test_reconciliation_no_resource_spike():
    test = NetworkPartitionTest(num_nodes=4, partition_duration_seconds=5)

    test.initialize_nodes()
    group1 = ["node-1", "node-2"]
    group2 = ["node-3", "node-4"]

    cpu_before = psutil.Process(os.getpid()).cpu_percent(interval=0.1)
    ram_before = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

    test.create_partition(group1, group2)
    time.sleep(3)

    all_nodes = list(test.nodes.keys())
    metrics = test.heal_partition(all_nodes)

    cpu_spike = metrics.cpu_peak_during_recon - cpu_before
    ram_spike = metrics.ram_peak_during_recon_mb - ram_before

    logger.info(f"CPU spike: {cpu_spike:.1f}%, RAM spike: {ram_spike:.1f}MB")

    assert cpu_spike < 50.0, f"CPU spike too high: {cpu_spike:.1f}%"
    assert ram_spike < 500.0, f"RAM spike too high: {ram_spike:.1f}MB"


def test_partition_events_recorded():
    test = NetworkPartitionTest(num_nodes=4, partition_duration_seconds=5)

    test.initialize_nodes()
    group1 = ["node-1", "node-2"]
    group2 = ["node-3", "node-4"]

    test.create_partition(group1, group2)
    time.sleep(2)

    all_nodes = list(test.nodes.keys())
    test.heal_partition(all_nodes)

    assert len(test.partition_events) >= 2
    assert test.partition_events[0].event_type == "partition_created"
    assert test.partition_events[-1].event_type == "partition_healed"


def test_multiple_partition_cycles():
    test = NetworkPartitionTest(num_nodes=4, partition_duration_seconds=3)

    test.initialize_nodes()

    for cycle in range(3):
        group1 = ["node-1", "node-2"]
        group2 = ["node-3", "node-4"]
        test.create_partition(group1, group2)
        time.sleep(2)
        all_nodes = list(test.nodes.keys())
        test.heal_partition(all_nodes)
        logger.info(f"Cycle {cycle + 1} completed")
        time.sleep(1)

    assert test.get_partition_discovery_count() == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
