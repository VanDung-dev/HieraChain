"""
Resource Monitoring Stress Tests.
Evaluates container CPU, memory, network I/O, and disk usage patterns
under variable request load to ensure physical resource safety boundaries.
"""

import os
import logging
import threading
import math
from dataclasses import dataclass, field
from typing import List

import pytest

from docker.stress.real_stress_client import NodeStatus
from docker.stress.resource_monitoring import ResourceStressTester, ResourceMetrics

logger = logging.getLogger(__name__)

# Configuration from environment or defaults
DEFAULT_NODES = os.getenv(
    "TARGET_NODES",
    "node1:2661,node2:2661,node3:2661,node4:2661"
).split(",")

TEST_DURATION = int(os.getenv("TEST_DURATION", "60"))
REAL_REQUESTS = os.getenv("REAL_REQUESTS", "true").lower() == "true"

# Default chain name for stress testing
DEFAULT_CHAIN_NAME = os.getenv("STRESS_CHAIN_NAME", "stress_test")

@dataclass
class ResourceStressTestResult:
    """Results from resource stress test with monitoring."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    nodes: dict[str, NodeStatus] = field(default_factory=dict)
    
    # Resource monitoring metrics
    metrics_history: List[ResourceMetrics] = field(default_factory=list)
    
    def __post_init__(self):
        self.lock = threading.Lock()
        
    def add_metric(self, metric: ResourceMetrics) -> None:
        with self.lock:
            self.metrics_history.append(metric)
            
    def get_avg_cpu_usage(self) -> float:
        """Get average CPU usage across all nodes."""
        if not self.metrics_history:
            return 0.0
        total = sum(m.cpu_usage for m in self.metrics_history)
        return total / len(self.metrics_history) if total > 0 else 0.0
    
    def get_avg_memory_usage(self) -> float:
        """Get average memory usage across all nodes."""
        if not self.metrics_history:
            return 0.0
        total = sum(m.memory_usage for m in self.metrics_history)
        return total / len(self.metrics_history) if total > 0 else 0.0
    
    def get_avg_disk_usage(self) -> float:
        """Get average disk usage across all nodes."""
        if not self.metrics_history:
            return 0.0
        total = sum(m.disk_usage for m in self.metrics_history)
        return total / len(self.metrics_history) if total > 0 else 0.0
    
    def get_avg_network_io(self) -> float:
        """Get average network IO across all nodes."""
        if not self.metrics_history:
            return 0.0
        total = sum(m.network_io for m in self.metrics_history)
        return total / len(self.metrics_history) if total > 0 else 0.0


class TestResourceMonitoring:
    """Test class for resource monitoring."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not os.path.exists("/var/run/docker.sock"):
            if os.getenv("HRC_STRESS_ENV") == "docker":
                pytest.fail("Docker stress requires the mounted Docker Engine socket")
            pytest.skip("Live resource metrics require the mounted Docker Engine socket")
        self.stress_tester = ResourceStressTester()
        self.node_status = {}
        
        # Initialize node status
        for node in DEFAULT_NODES:
            parts = node.split(":")
            port = int(parts[1]) if len(parts) > 1 else 2661
            if port == 80:
                continue
            node_id = parts[0]
            self.node_status[node_id] = NodeStatus(node_id=node_id, url=f"http://{node}")

    def _assert_live_metrics(self, results):
        expected_nodes = set(self.stress_tester.node_status)
        assert results.total_requests > 0
        assert results.successful_requests > 0
        assert results.successful_requests + results.failed_requests == results.total_requests
        assert results.avg_response_time > 0
        assert results.metrics_history
        assert {metric.node_id for metric in results.metrics_history} == expected_nodes
        assert all(
            metric.memory_usage > 0
            and all(math.isfinite(value) and value >= 0 for value in (
                metric.cpu_usage, metric.disk_usage, metric.network_io
            ))
            for metric in results.metrics_history
        ), "Docker resource counters must contain finite, non-default measurements"
        
    def test_cpu_usage_monitoring(self):
        """Test CPU usage monitoring."""
        # Run test for 30 seconds
        results = self.stress_tester.run_resource_stress_test(30)
        
        self._assert_live_metrics(results)
        
        # Get average CPU usage
        avg_cpu = results.get_avg_cpu_usage()
        
        logger.info("Average CPU usage: %.1f%%", avg_cpu)
        
    def test_memory_usage_monitoring(self):
        """Test memory usage monitoring."""
        # Run test for 30 seconds
        results = self.stress_tester.run_resource_stress_test(30)
        
        self._assert_live_metrics(results)
        
        # Get average memory usage
        avg_memory = results.get_avg_memory_usage()
        
        logger.info("Average Memory usage: %.1fMB", avg_memory)
        
    def test_disk_usage_monitoring(self):
        """Test disk usage monitoring."""
        # Run test for 30 seconds
        results = self.stress_tester.run_resource_stress_test(30)
        
        self._assert_live_metrics(results)
        
        # Get average disk usage
        avg_disk = results.get_avg_disk_usage()
        
        logger.info("Average block I/O: %.3fMB/s", avg_disk)
        
    def test_network_io_monitoring(self):
        """Test network IO monitoring."""
        # Run test for 30 seconds
        results = self.stress_tester.run_resource_stress_test(30)
        
        self._assert_live_metrics(results)
        
        # Get average network IO
        avg_network = results.get_avg_network_io()
        
        logger.info("Average Network IO: %.1fMB/s", avg_network)
        
    def test_combined_resource_monitoring(self):
        """Test combined resource monitoring."""
        # Run test for 45 seconds
        results = self.stress_tester.run_resource_stress_test(45)
        
        self._assert_live_metrics(results)
        
        # Get average metrics
        avg_cpu = results.get_avg_cpu_usage()
        avg_memory = results.get_avg_memory_usage()
        avg_disk = results.get_avg_disk_usage()
        avg_network = results.get_avg_network_io()
        
        logger.info("Resource Monitoring Results:")
        logger.info("Average CPU usage: %.1f%%", avg_cpu)
        logger.info("Average Memory usage: %.1fMB", avg_memory)
        logger.info("Average block I/O: %.1fMB/s", avg_disk)
        logger.info("Average Network IO: %.1fMB/s", avg_network)
        
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run all resource monitoring tests
    pytest.main([__file__, "-v", "-s"])
