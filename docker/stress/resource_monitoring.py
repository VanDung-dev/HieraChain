"""
Resource Monitoring Core utilities.
Collects and aggregates CPU, Memory, Disk, and Network IO metrics from nodes
during stress test executions to generate system consumption reports.
"""

import os
import time
import logging
import threading
import random
import json
import requests
from requests.adapters import HTTPAdapter
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from docker.stress.real_stress_client import NodeStatus

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
class ResourceMetrics:
    """Resource metrics for a node."""
    node_id: str
    cpu_usage: float = 0.0  # %
    memory_usage: float = 0.0  # MB
    disk_usage: float = 0.0  # block I/O MB/s
    network_io: float = 0.0  # MB/s
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        self.lock = threading.Lock()

@dataclass
class ResourceMonitoringResult:
    """Results from resource monitoring test."""
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
        return total / len(self.metrics_history)
    
    def get_avg_memory_usage(self) -> float:
        """Get average memory usage across all nodes."""
        if not self.metrics_history:
            return 0.0
        total = sum(m.memory_usage for m in self.metrics_history)
        return total / len(self.metrics_history)
    
    def get_avg_disk_usage(self) -> float:
        """Get average disk usage across all nodes."""
        if not self.metrics_history:
            return 0.0
        total = sum(m.disk_usage for m in self.metrics_history)
        return total / len(self.metrics_history)
    
    def get_avg_network_io(self) -> float:
        """Get average network IO across all nodes."""
        if not self.metrics_history:
            return 0.0
        total = sum(m.network_io for m in self.metrics_history)
        return total / len(self.metrics_history)
    
    def print_summary(self) -> None:
        """Print resource monitoring summary."""
        print("\n" + "=" * 60)
        print("  RESOURCE MONITORING SUMMARY")
        print("=" * 60)
        print(f"Test Duration:     {self.duration:.2f}s")
        print(f"Total Requests:    {self.total_requests}")
        print(f"Successful:        {self.successful_requests}")
        print(f"Failed:            {self.failed_requests}")
        print(f"Avg Response Time:   {self.avg_response_time*1000:.2f}ms")
        print()
        print("--- Resource Metrics ---")
        for metric in self.metrics_history:
            print(
                f"  {metric.node_id}: {metric.cpu_usage:.1f}% CPU, "
                f"{metric.memory_usage:.1f}MB RAM, "
                f"{metric.disk_usage:.3f}MB/s block I/O, "
                f"{metric.network_io:.3f}MB/s network I/O"
            )
        print("=" * 60)

class ResourceMonitor:
    def __init__(self, nodes: Optional[List[str]] = None, result: Optional[ResourceMonitoringResult] = None, interval: float = 5.0):
        self.nodes = nodes or DEFAULT_NODES
        self.interval = interval
        self.result = result or ResourceMonitoringResult()
        self.metrics: Dict[str, ResourceMetrics] = {}
        self.running = False
        self.thread = None
        self.errors: list[str] = []
        self.previous_io: dict[str, tuple[float, int, int]] = {}
    
    def _collect_metrics(self) -> None:
        """Collect metrics from all nodes."""
        while self.running:
            for node in self.nodes:
                try:
                    metric = self._get_container_metrics(node)
                except Exception as exc:
                    self.errors.append(str(exc))
                    logger.exception("Failed to collect live Docker metrics for %s", node)
                    self.running = False
                    return

                self.metrics[node] = metric
                self.result.add_metric(metric)
            
            # Wait for next interval
            time.sleep(self.interval)
    
    def _get_container_metrics(self, node_id: str) -> ResourceMetrics:
        """Read actual per-container metrics from the mounted Docker Engine socket."""
        from docker.stress.docker_helper import get_docker_client

        container = f"hierachain-{node_id}"
        status, payload = get_docker_client().request(
            "GET", f"/v1.41/containers/{container}/stats?stream=false"
        )
        if status != 200:
            raise RuntimeError(f"Docker stats for {container} returned HTTP {status}: {payload}")

        stats = json.loads(payload)
        cpu = stats["cpu_stats"]
        previous_cpu = stats["precpu_stats"]
        cpu_delta = cpu["cpu_usage"]["total_usage"] - previous_cpu["cpu_usage"]["total_usage"]
        system_delta = cpu["system_cpu_usage"] - previous_cpu["system_cpu_usage"]
        if cpu_delta < 0 or system_delta <= 0:
            raise RuntimeError(f"Docker returned an invalid CPU sample for {container}")
        cpu_count = cpu.get("online_cpus") or len(cpu["cpu_usage"].get("percpu_usage", [])) or 1
        cpu_usage = cpu_delta / system_delta * cpu_count * 100

        memory_usage = stats["memory_stats"]["usage"] / (1024 * 1024)
        networks = stats.get("networks")
        if not networks:
            raise RuntimeError(f"Docker returned no network counters for {container}")
        received = sum(interface["rx_bytes"] for interface in networks.values())
        transmitted = sum(interface["tx_bytes"] for interface in networks.values())
        block_io = stats["blkio_stats"].get("io_service_bytes_recursive")
        if block_io is None:
            raise RuntimeError(f"Docker returned no block I/O counters for {container}")
        disk_bytes = sum(item["value"] for item in block_io if item["op"].lower() in {"read", "write"})

        now = time.monotonic()
        previous = self.previous_io.get(node_id)
        network_rate = disk_rate = 0.0
        if previous:
            previous_time, previous_network, previous_disk = previous
            elapsed = now - previous_time
            if elapsed <= 0:
                raise RuntimeError(f"Invalid Docker sampling interval for {container}")
            network_rate = max(0, received + transmitted - previous_network) / (1024 * 1024 * elapsed)
            disk_rate = max(0, disk_bytes - previous_disk) / (1024 * 1024 * elapsed)
        self.previous_io[node_id] = (now, received + transmitted, disk_bytes)

        return ResourceMetrics(
            node_id=node_id,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_rate,
            network_io=network_rate,
            timestamp=time.time(),
        )

    def start(self) -> None:
        """Start resource monitoring."""
        self.running = True
        self.thread = threading.Thread(target=self._collect_metrics, daemon=True)
        self.thread.start()
        
    def stop(self) -> None:
        """Stop resource monitoring."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10 * len(self.nodes) + self.interval + 1)
            self.thread = None

@dataclass
class ResourceStressTester:
    """Tester for resource stress with monitoring."""
    nodes: list[str] = field(default_factory=lambda: os.getenv("TARGET_NODES", "node1:2661,node2:2661,node3:2661,node4:2661").split(","))
    timeout: float = 15.0
    result: ResourceMonitoringResult = field(default_factory=ResourceMonitoringResult)
    monitor: ResourceMonitor = field(init=False)
    node_status: dict[str, NodeStatus] = field(default_factory=dict, init=False)
    
    def __post_init__(self) -> None:
        """Initialize stress tester with resource monitor."""
        if not REAL_REQUESTS:
            raise RuntimeError("Docker resource stress requires REAL_REQUESTS=true")
        self.session = self._setup_session()
        self.node_status = {}
        for node in self.nodes:
            parts = node.split(":")
            port = int(parts[1]) if len(parts) > 1 else 2661
            if port == 80:
                continue
            node_id = parts[0]
            self.node_status[node_id] = NodeStatus(node_id=node_id, url=f"http://{node}")
        self.monitor = ResourceMonitor(list(self.node_status), self.result)
    
    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry and backoff."""
        session = requests.Session()
        
        # Increase connection pool for concurrent workers
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=5)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            "User-Agent": "HieraChain-Stress-Tester/1.0",
            "Content-Type": "application/json",
        })
        
        # Add API Key if provided in environment
        api_key = os.getenv("HRC_API_KEY")
        if api_key:
            key_name = os.getenv("HRC_API_KEY_NAME", "X-API-Key")
            session.headers.update({key_name: api_key})
        
        return session
    
    def _send_request(self, node_id: str) -> None:
        """Send a request to a node."""
        status = self.node_status[node_id]
        started = time.monotonic()
        try:
            # Randomly select an endpoint
            endpoints = ["/api/ledger/health", "/api/admin/status", "/"]
            endpoint = random.choice(endpoints)
            
            url = f"http://{node_id}:2661{endpoint}"
            response = self.session.get(url, timeout=15)
            
            # Process response
            if response.status_code in (200, 201, 202):
                self.result.successful_requests += 1
            else:
                self.result.failed_requests += 1
                
        except requests.RequestException as e:
            self.result.failed_requests += 1
        finally:
            status.response_times.append(time.monotonic() - started)

        # Update result
        self.result.total_requests += 1
        
    def run_resource_stress_test(self, duration: float = 60.0) -> ResourceMonitoringResult:
        """Run resource stress test with monitoring."""
        logger.info("Starting resource stress test...")
        logger.info(f"Test duration: {duration}s")
        
        try:
            logger.info("Waiting for nodes to become healthy...")
            if not self._wait_for_nodes(timeout=60):
                raise RuntimeError("Docker resource stress requires all configured nodes to be healthy")

            self.monitor.start()
            start_time = time.time()
            logger.info("Running test for %d seconds...", duration)
            while time.time() - start_time < duration:
                if self.monitor.errors:
                    raise RuntimeError(self.monitor.errors[0])
                for node_id in self.node_status:
                    self._send_request(node_id)
                time.sleep(0.1)
        finally:
            self.monitor.stop()

        if self.monitor.errors:
            raise RuntimeError(self.monitor.errors[0])
        if self.result.total_requests == 0 or self.result.successful_requests == 0:
            raise RuntimeError("Resource stress generated no successful live HTTP requests")
        if self.result.successful_requests + self.result.failed_requests != self.result.total_requests:
            raise RuntimeError("Resource stress request counters do not reconcile")
        
        # Calculate averages
        self.result.duration = time.time() - start_time
        self.result.avg_response_time = self._calculate_avg_response_time()
        
        return self.result
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time from all requests."""
        response_times = [
            elapsed
            for status in self.node_status.values()
            for elapsed in status.response_times
        ]
        if not response_times:
            return 0.0
        return sum(response_times) / len(response_times)

    def _wait_for_nodes(self, timeout: float = 30.0, min_healthy: int | None = None) -> bool:
        """
        Wait for nodes to become healthy.
        
        Args:
            timeout: Maximum time to wait in seconds.
            min_healthy: Minimum number of healthy nodes required. 
                        If None, requires all nodes to be healthy.
        """
        if min_healthy is None:
            min_healthy = len(self.node_status)
            
        logger.info("Waiting for %d/%d nodes to be healthy (timeout=%ds)...",
                   min_healthy, len(self.node_status), timeout)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check health of all nodes
            healthy = 0
            for node_id in self.node_status:
                if self._check_node_health(node_id):
                    healthy += 1
            
            if healthy >= min_healthy:
                logger.info("Cluster ready: %d nodes healthy", healthy)
                return True
            
            # Wait for next check
            time.sleep(2.0)
        
        return False
    
    def _check_node_health(self, node_id: str) -> bool:
        """Check if a node is healthy."""
        try:
            # Use correct API endpoint
            url = f"http://{node_id}:2661/api/ledger/health"
            response = self.session.get(url, timeout=15)
            
            # Update node status
            if response.status_code == 200:
                self.node_status[node_id].is_healthy = True
                return True
            
        except requests.RequestException:
            pass
        
        # Mark as unhealthy
        self.node_status[node_id].is_healthy = False
        return False

    def print_results(self) -> None:
        """Print test results summary."""
        self.result.print_summary()


def test_resource_stress():
    """Run resource stress tests with monitoring."""
    # Test configurations
    test_configs = [
        {"duration": 30, "nodes": ["node1:2661", "node2:2661"]},
        {"duration": 45, "nodes": ["node3:2661", "node4:2661"]},
        {"duration": 60, "nodes": ["node1:2661", "node2:2661", "node3:2661", "node4:2661"]},
    ]
    
    # Run tests for each configuration
    for config in test_configs:
        logger.info("Running resource stress test: %s", config)
        
        # Run test
        results = ResourceStressTester(
            nodes=config.get("nodes"),
            timeout=config.get("timeout", 15.0)
        ).run_resource_stress_test(config.get("duration", 60))
        
        # Log results
        logger.info("Resource stress test completed: %s", config)
        logger.info("Duration: %.2fs", results.duration)
        logger.info("Total Requests: %d", results.total_requests)
        logger.info("Successful: %d (%.1f%%)", results.successful_requests, (results.successful_requests / results.total_requests * 100) if results.total_requests > 0 else 0)
        logger.info("Failed: %d (%.1f%%)", results.failed_requests, (results.failed_requests / results.total_requests * 100) if results.total_requests > 0 else 0)
        
        # Validate minimum success rate
        if results.total_requests > 0:
            success_rate = results.successful_requests / results.total_requests
            logger.info("Success rate: %.1f%%", success_rate * 100)
            
            # Allow lower success rate for stress tests
            if success_rate < 0.5:
                logger.warning("Low success rate: %.1f%%", success_rate * 100)
                
        # Print detailed results
        results.print_summary()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run all resource stress tests
    test_resource_stress()
    
    print("\nAll resource stress tests completed successfully.")
    print("=" * 60)
