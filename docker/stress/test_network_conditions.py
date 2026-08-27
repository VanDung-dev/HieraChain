"""
Network Conditions Stress Tests.
Simulates network degradation (latency, jitter, packet loss, congestion, bandwidth limits)
on HieraChain API endpoints and measures success rates and response times.
"""

import os
import time
import random
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
import requests.exceptions
from requests.adapters import HTTPAdapter, Retry

from docker.stress.real_stress_client import RealStressClient, NodeStatus

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
class NetworkCondition:
    """Network condition for stress testing."""
    condition_type: str  # e.g., "latency", "packet_loss", "jitter", etc.
    config: Dict[str, Any]  # Configuration parameters for the condition
    description: str = ""  # Description of the condition
    severity: int = 0  # Severity level (0-100)

    def apply(self, client: RealStressClient) -> None:
        """Apply the network condition to the stress test client."""
        if self.condition_type == "latency":
            client.simulate_latency(self.config)
        elif self.condition_type == "packet_loss":
            client.simulate_packet_loss(self.config)
        elif self.condition_type == "jitter":
            client.simulate_jitter(self.config)
        elif self.condition_type == "congestion":
            client.simulate_congestion(self.config)
        elif self.condition_type == "bandwidth":
            client.simulate_bandwidth(self.config)
        else:
            logger.warning(f"Unknown network condition: {self.condition_type}")

@dataclass
class NetworkStressTestResult:
    """Results from network stress test."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    nodes: dict[str, NodeStatus] = field(default_factory=dict)
    
    # Network stress test metrics
    network_conditions: list[NetworkCondition] = field(default_factory=list)
    network_config: Dict[str, Any] = field(default_factory=dict)
    network_type: str = ""
    network_stats: Dict[str, Any] = field(default_factory=dict)

class NetworkStressTester:
    def __init__(self, nodes: Optional[List[str]] = None, timeout: float = 15.0):
        self.nodes = nodes or DEFAULT_NODES
        self.timeout = timeout
        self.node_status: dict[str, NodeStatus] = {}
        self.results = NetworkStressTestResult()
        self.session = self._setup_session()
        self.lock = threading.Lock()
        self.latency_sim = 0.0
        self.packet_loss_rate = 0
        self.jitter_sim = 0.0
        self.congestion_rate = 0
        self.bandwidth_limit_rate = 0
        self._setup_node_status()
        
    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry and backoff."""
        session = requests.Session()
        
        # Increase connection pool for concurrent workers
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=Retry(
            total=5,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "POST", "PATCH", "DELETE"]
        ))
        
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
    
    def _setup_node_status(self) -> None:
        """Initialize node status — exclude gateway (port 80, non-API)."""
        for node in self.nodes:
            parts = node.split(":")
            port = int(parts[1]) if len(parts) > 1 else 2661
            if port == 80:
                continue
            node_id = parts[0]
            url = f"http://{node}"
            self.node_status[node_id] = NodeStatus(node_id=node_id, url=url)
    
    def check_health(self, node_id: str) -> bool:
        """Check if a node is healthy by trying multiple system endpoints."""
        status = self.node_status.get(node_id)
        if not status:
            return False
        
        # Endpoints to try in order of preference
        endpoints = ["/api/admin/status", "/api/ledger/health", "/"]
        
        for endpoint in endpoints:
            try:
                url = f"{status.url}{endpoint}"
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    status.is_healthy = True
                    return True
            except requests.RequestException as e:
                logger.debug(f"Endpoint {endpoint} failed for {node_id}: {e}")
                continue
        
        # If we reach here, all endpoints failed
        status.is_healthy = False
        logger.warning(f"❌ Node {node_id} is UNHEALTHY (all endpoints failed at {status.url})")
        return False
    
    def check_all_nodes(self) -> dict[str, bool]:
        """Check health of all nodes."""
        _results = {}
        for node_id in self.node_status:
            _results[node_id] = self.check_health(node_id)
        return _results
    
    def apply_network_condition(self, condition: NetworkCondition) -> None:
        """Apply a network condition to the stress test."""
        condition.apply(self)

    def simulate_latency(self, config: Dict[str, Any]) -> None:
        self.latency_sim = config.get("base_latency", 100) / 1000.0 + random.randint(0, config.get("extra_latency", 200)) / 1000.0

    def simulate_packet_loss(self, config: Dict[str, Any]) -> None:
        self.packet_loss_rate = config.get("loss_rate", 5)

    def simulate_jitter(self, config: Dict[str, Any]) -> None:
        self.jitter_sim = config.get("base_jitter", 50) / 1000.0 + random.randint(0, config.get("extra_jitter", 100)) / 1000.0

    def simulate_congestion(self, config: Dict[str, Any]) -> None:
        self.congestion_rate = config.get("base_congestion", 30) + random.randint(0, config.get("extra_congestion", 20))

    def simulate_bandwidth(self, config: Dict[str, Any]) -> None:
        self.bandwidth_limit_rate = config.get("base_bandwidth", 1) + random.randint(0, config.get("extra_bandwidth", 2))
    
    def run_network_stress_test(self, condition: NetworkCondition) -> NetworkStressTestResult:
        """Run network stress test with a specific condition."""
        logger.info("Starting network stress test...")
        logger.info(f"Network condition: {condition.condition_type} {condition.config}")
        
        start_time = time.time()
        
        # Wait for nodes to be healthy
        logger.info("Waiting for nodes to become healthy...")
        if not self._wait_for_nodes(timeout=60):
            logger.warning("Not all nodes are healthy, proceeding anyway")
        
        # Apply network condition
        self.apply_network_condition(condition)
        
        # Run test for the duration
        while time.time() - start_time < TEST_DURATION:
            # Send requests to all nodes
            for node_id in self.node_status:
                self._send_request(node_id)
            
            # Wait for requests to complete
            time.sleep(0.1)
        
        # Calculate averages
        self._calculate_response_times()
        
        # Set test duration
        self.results.duration = time.time() - start_time
        self.results.network_conditions.append(condition)
        
        return self.results
    
    def _send_request(self, node_id: str) -> None:
        """Send a request to a node."""
        status = self.node_status.get(node_id)
        if not status:
            return
        
        # Simulate packet loss / congestion / bandwidth failures
        if self.packet_loss_rate > 0 and random.randint(1, 100) <= self.packet_loss_rate:
            with self.lock:
                status.error_count += 1
                status.last_error = "Simulated packet loss"
                self.results.failed_requests += 1
            return
        if self.congestion_rate > 0 and random.randint(1, 100) <= self.congestion_rate:
            with self.lock:
                status.error_count += 1
                status.last_error = "Simulated network congestion"
                self.results.failed_requests += 1
            return
        if self.bandwidth_limit_rate > 0 and random.randint(1, 100) <= self.bandwidth_limit_rate:
            with self.lock:
                status.error_count += 1
                status.last_error = "Simulated network bandwidth limit"
                self.results.failed_requests += 1
            return

        # Simulate latency / jitter delay
        delay = self.latency_sim + self.jitter_sim
        if delay > 0:
            time.sleep(delay)

        # Randomly select an endpoint
        endpoints = ["/api/ledger/health", "/api/admin/status", "/"]
        endpoint = random.choice(endpoints)
        
        try:
            start = time.time()
            response = self.session.get(f"{status.url}{endpoint}", timeout=self.timeout)
            elapsed = time.time() - start
            
            with self.lock:
                status.response_times.append(elapsed)
                if response.status_code in (200, 201, 202):
                    status.success_count += 1
                    self.results.successful_requests += 1
                else:
                    status.error_count += 1
                    status.last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                    self.results.failed_requests += 1
                    
        except requests.RequestException as e:
            with self.lock:
                status.error_count += 1
                status.last_error = str(e)
                self.results.failed_requests += 1

    def _calculate_response_times(self) -> None:
        """Calculate average response times from all nodes."""
        all_times = []
        for status in self.node_status.values():
            all_times.extend(status.response_times)
            self.results.nodes[status.node_id] = status
        
        if all_times:
            self.results.avg_response_time = sum(all_times) / len(all_times)

    def _select_random_healthy_node(self) -> Optional[str]:
        """Select a random healthy node for sending requests."""
        healthy = [
            nid for nid, s in self.node_status.items()
            if s.is_healthy
        ]
        if not healthy:
            return None
        return random.choice(healthy)

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
            healthy = sum(1 for nid in self.node_status if self.check_health(nid))
            if healthy >= min_healthy:
                logger.info("Cluster ready: %d nodes healthy", healthy)
                return True
            time.sleep(2.0)
        
        return False

    def print_results(self) -> None:
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("  NETWORK STRESS TEST RESULTS")
        print("=" * 60)
        print(f"Test Duration:     {self.results.duration:.2f}s")
        print(f"Total Requests:    {self.results.total_requests}")
        print(f"Successful:        {self.results.successful_requests}")
        print(f"Failed:            {self.results.failed_requests}")
        print(f"Avg Response Time:   {self.results.avg_response_time*1000:.2f}ms")
        print()
        print("--- Node Status ---")
        for node_id, status in self.node_status.items():
            health = "✅" if status.is_healthy else "❌"
            print(f"  {health} {node_id}:")
            print(f"      Success: {status.success_count}")
            print(f"      Errors:  {status.error_count}")
            if status.response_times:
                avg = sum(status.response_times) / len(status.response_times)
                print(f"      Avg RT:  {avg*1000:.2f}ms")
            if status.last_error:
                print(f"      Error:   {status.last_error}")
        print("=" * 60)


def test_network_stress():
    """Run network stress tests with different conditions."""
    # Test configurations
    test_configs = [
        NetworkCondition(condition_type="latency", config={"base_latency": 200, "extra_latency": 100}, description="High latency network", severity=70),
        NetworkCondition(condition_type="packet_loss", config={"loss_rate": 5}, description="Packet loss network", severity=80),
        NetworkCondition(condition_type="jitter", config={"base_jitter": 50, "extra_jitter": 100}, description="Jitter network", severity=60),
        NetworkCondition(condition_type="congestion", config={"base_congestion": 30, "extra_congestion": 20}, description="Congestion network", severity=90),
        NetworkCondition(condition_type="bandwidth", config={"base_bandwidth": 1, "extra_bandwidth": 2}, description="Bandwidth limited network", severity=60),
    ]
    
    # Run tests for each configuration
    for test_config in test_configs:
        logger.info("Running network stress test: %s", test_config.condition_type)
        tester = NetworkStressTester(nodes=DEFAULT_NODES)
        results = tester.run_network_stress_test(test_config)
        
        # Log results
        logger.info("Network stress test completed: %s", test_config.condition_type)
        logger.info("Duration: %.2fs", results.duration)
        logger.info("Total Requests: %d", results.total_requests)
        logger.info("Successful: %d (%.1f%%)", results.successful_requests, (results.successful_requests / results.total_requests * 100) if results.total_requests > 0 else 0)
        logger.info("Failed: %d (%.1f%%)", results.failed_requests, (results.failed_requests / results.total_requests * 100) if results.total_requests > 0 else 0)
        
        # Validate minimum success rate
        if results.total_requests > 0:
            success_rate = results.successful_requests / results.total_requests
            logger.info("Success rate: %.1f%%", success_rate * 100)
            
            # Allow lower success rate for stress tests
            if test_config.condition_type in ("latency", "congestion", "bandwidth"):
                assert success_rate >= 0.5, f"Too many failures: {success_rate*100:.1f}% success"
            else:
                assert success_rate >= 0.8, f"Too many failures: {success_rate*100:.1f}% success"
        
        # Print detailed results
        tester.print_results()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run all network stress tests
    test_network_stress()
    
    print("\nAll network stress tests completed successfully.")
    print("=" * 60)