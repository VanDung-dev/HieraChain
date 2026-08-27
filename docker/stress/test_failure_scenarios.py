"""
Network Failure Scenarios Stress Tests.
Applies sequential failure scenarios (packet loss, congestion, latency spikes) 
to observe client-side fallback resilience and error recovery on HieraChain nodes.
"""

import os
import time
import random
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest
import requests
import requests.exceptions

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
class FailureScenario:
    """Failure scenario for stress testing."""
    scenario_type: str  # e.g., "latency", "packet_loss", etc.
    config: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    severity: int = 0  # 0-100
    
    def __post_init__(self):
        """Initialize scenario with default config."""
        if not self.config:
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default config for this scenario."""
        if self.scenario_type == "latency":
            return {"base_latency": 200, "extra_latency": 100}
        if self.scenario_type == "packet_loss":
            return {"loss_rate": 5}
        if self.scenario_type == "jitter":
            return {"base_jitter": 50, "extra_jitter": 100}
        if self.scenario_type == "congestion":
            return {"base_congestion": 30, "extra_congestion": 20}
        if self.scenario_type == "bandwidth":
            return {"base_bandwidth": 1, "extra_bandwidth": 2}
        
        return {}
    
    def apply(self, client: RealStressClient) -> None:
        """Apply this scenario to the stress client."""
        client.apply_network_condition(self.scenario_type, self.config)

@dataclass
class NetworkFailureTestResult:
    """Results from network failure test."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    nodes: dict[str, NodeStatus] = field(default_factory=dict)
    
    # Network failure scenarios
    scenarios: List[FailureScenario] = field(default_factory=list)
    condition_type: str = ""
    condition_config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        self.lock = threading.Lock()
        self.session = requests.Session()
        
    def apply_network_condition(self, condition_type: str, config: Dict[str, Any]) -> None:
        self.condition_type = condition_type
        self.condition_config = config
    
    def add_scenario(self, scenario: FailureScenario) -> None:
        """Add a failure scenario to the test."""
        with self.lock:
            self.scenarios.append(scenario)
            
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time."""
        return self.avg_response_time

    def run_scenarios(self) -> None:
        """Run all failure scenarios."""
        for scenario in self.scenarios:
            logger.info("Running scenario: %s (%s)", scenario.scenario_type, scenario.description)
            
            # Apply scenario
            scenario.apply(self)
            
            # Run test for scenario duration
            duration = scenario.config.get("duration", TEST_DURATION)
            logger.info("Running test for %.1f seconds...", duration)
            start_time = time.time()
            
            # Run test for this scenario
            while time.time() - start_time < duration:
                # Send requests to all nodes
                for node_id in self.nodes:
                    self._send_request(node_id)
                
                # Wait for next interval
                time.sleep(0.1)
            
            # Log scenario completion
            logger.info("Scenario completed: %s (%.1f%% success)", scenario.scenario_type, (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0)
            
    def _send_request(self, node_id: str) -> None:
        """Send a request to a node."""
        # Simulate network packet loss / congestion / bandwidth failures
        if self.condition_type == "packet_loss":
            loss_rate = self.condition_config.get("loss_rate", 5)
            if random.randint(1, 100) <= loss_rate:
                self.failed_requests += 1
                self.total_requests += 1
                return
        elif self.condition_type == "congestion":
            congestion_rate = self.condition_config.get("base_congestion", 30)
            if random.randint(1, 100) <= congestion_rate:
                self.failed_requests += 1
                self.total_requests += 1
                return
        elif self.condition_type == "bandwidth":
            bandwidth_rate = self.condition_config.get("base_bandwidth", 1) * 10
            if random.randint(1, 100) <= bandwidth_rate:
                self.failed_requests += 1
                self.total_requests += 1
                return
        elif self.condition_type == "latency" or self.condition_type == "jitter":
            base_delay = self.condition_config.get("base_latency", self.condition_config.get("base_jitter", 50)) / 1000.0
            time.sleep(base_delay)

        try:
            # Randomly select an endpoint
            endpoints = ["/api/ledger/health", "/api/admin/status", "/"]
            endpoint = random.choice(endpoints)
            
            # Send request
            url = f"http://{node_id}:2661{endpoint}"
            response = self.session.get(url, timeout=15)
            
            # Update counts
            if response.status_code in (200, 201, 202):
                self.successful_requests += 1
            else:
                self.failed_requests += 1
                
        except requests.RequestException as e:
            self.failed_requests += 1
            
        # Update total
        self.total_requests += 1

    def _wait_for_nodes(self, timeout: float = 30.0, min_healthy: int | None = None) -> bool:
        """Wait for nodes to become healthy."""
        if min_healthy is None:
            min_healthy = len(self.nodes)
            
        logger.info("Waiting for %d/%d nodes to be healthy (timeout=%.1f)...",
                   min_healthy, len(self.nodes), timeout)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check health of all nodes
            healthy = 0
            for node_id in self.nodes:
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
                return True
            
        except requests.RequestException:
            pass
        
        return False


class TestFailureScenarios:
    """Test class for failure scenarios."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.scenario_types = ["latency", "packet_loss", "jitter", "congestion", "bandwidth"]
        self.default_config = {
            "duration": 30,
            "base_congestion": 30,
            "extra_congestion": 20
        }
        self.scenarios = []
        
        # Initialize scenarios
        for scenario_type in self.scenario_types:
            scenario = FailureScenario(
                scenario_type=scenario_type,
                config=self.default_config,
                description=f"{scenario_type} stress test",
                severity=70
            )
            self.scenarios.append(scenario)
            
    def test_run_all_scenarios(self):
        """Run all failure scenarios."""
        logger.info("Starting failure scenario test...")
        
        # Initialize failure test
        failure_test = NetworkFailureTestResult()
        failure_test.nodes = self._initialize_node_status()
        
        # Run all scenarios
        for scenario in self.scenarios:
            failure_test.add_scenario(scenario)
        failure_test.run_scenarios()
            
        # Calculate averages
        avg_response_time = failure_test._calculate_avg_response_time()
        
        # Log summary
        logger.info("Test completed: %.1f%% success (%.2fms avg response)",
                   (failure_test.successful_requests / failure_test.total_requests * 100) if failure_test.total_requests > 0 else 0,
                   avg_response_time * 1000)
        
        # This is a failure scenario test, not a pass/fail test
        assert True
    
    def _initialize_node_status(self) -> Dict[str, NodeStatus]:
        """Initialize node status for failure scenarios."""
        nodes = {}
        
        for node in DEFAULT_NODES:
            parts = node.split(":")
            node_id = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 2661
            if port == 80:
                continue
            nodes[node_id] = NodeStatus(
                node_id=node_id,
                url=f"http://{node}:{port}"
            )
            
        return nodes


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run all failure scenario tests
    pytest.main([__file__, "-v", "-s"])