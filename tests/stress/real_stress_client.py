"""
Real Stress Test Client.

Sends actual HTTP requests to HieraChain nodes for stress testing.
This replaces the simulation-based tests with real network requests.
"""

import os
import time
import random
import hashlib
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Configuration from environment or defaults
# Use port 2661 which is the default API_PORT from settings.py
DEFAULT_NODES = os.getenv(
    "TARGET_NODES",
    "node1:2661,node2:2661,node3:2661,node4:2661"
).split(",")

TEST_DURATION = int(os.getenv("TEST_DURATION", "60"))
REAL_REQUESTS = os.getenv("REAL_REQUESTS", "true").lower() == "true"

# Default chain name for stress testing
DEFAULT_CHAIN_NAME = os.getenv("STRESS_CHAIN_NAME", "stress_test")


@dataclass
class NodeStatus:
    """Status of a HieraChain node."""
    node_id: str
    url: str
    is_healthy: bool = False
    response_times: list[float] = field(default_factory=list)
    success_count: int = 0
    error_count: int = 0
    last_error: str = ""


@dataclass
class StressTestResult:
    """Results from stress test."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    events_submitted: int = 0
    events_confirmed: int = 0
    nodes: dict[str, NodeStatus] = field(default_factory=dict)


class RealStressClient:
    """Client for real stress testing against HieraChain nodes."""

    def __init__(
        self,
        nodes: list[str] | None = None,
        timeout: float = 5.0,
    ):
        self.nodes = nodes or DEFAULT_NODES
        self.timeout = timeout
        self.node_status: dict[str, NodeStatus] = {}
        self.lock = threading.Lock()
        self.results = StressTestResult()

        # Initialize node status
        for node in self.nodes:
            node_id = node.split(":")[0]
            url = f"http://{node}"
            self.node_status[node_id] = NodeStatus(node_id=node_id, url=url)

    def check_health(self, node_id: str) -> bool:
        """Check if a node is healthy."""
        status = self.node_status.get(node_id)
        if not status:
            return False

        try:
            # Use correct API endpoint from hierachain.api.v1.endpoints
            response = requests.get(
                f"{status.url}/api/v1/health",
                timeout=self.timeout,
            )
            status.is_healthy = response.status_code == 200
            return status.is_healthy
        except requests.RequestException as e:
            status.is_healthy = False
            status.last_error = str(e)
            return False

    def check_all_nodes(self) -> dict[str, bool]:
        """Check health of all nodes."""
        results = {}
        for node_id in self.node_status:
            results[node_id] = self.check_health(node_id)
        return results

    def wait_for_nodes(self, timeout: float = 60.0) -> bool:
        """Wait for all nodes to become healthy."""
        start = time.time()
        while time.time() - start < timeout:
            health = self.check_all_nodes()
            if all(health.values()):
                logger.info("All nodes are healthy")
                return True
            logger.info("Waiting for nodes: %s", health)
            time.sleep(2)
        return False

    def generate_event(self) -> dict[str, Any]:
        """Generate a valid event for submission matching EventRequest schema."""
        event_id = hashlib.sha256(
            f"{time.time()}-{random.random()}".encode()
        ).hexdigest()[:16]

        # Match EventRequest schema from hierachain.api.v1.schemas
        return {
            "entity_id": f"stress_entity_{event_id}",
            "event_type": "stress_test",
            "details": {
                "data": f"stress_test_data_{random.randint(1, 10000)}",
                "size": random.randint(100, 1000),
                "timestamp": time.time(),
            },
        }

    def submit_event(
        self,
        node_id: str,
        event: dict[str, Any],
        chain_name: str = DEFAULT_CHAIN_NAME,
    ) -> bool:
        """Submit an event to a node's chain."""
        status = self.node_status.get(node_id)
        if not status:
            return False

        start_time = time.time()
        try:
            # Use correct API endpoint: POST /api/v1/chains/{chain_name}/events
            response = requests.post(
                f"{status.url}/api/v1/chains/{chain_name}/events",
                json=event,
                timeout=self.timeout,
            )
            elapsed = time.time() - start_time

            with self.lock:
                status.response_times.append(elapsed)
                if response.status_code in (200, 201, 202):
                    status.success_count += 1
                    self.results.successful_requests += 1
                    self.results.events_submitted += 1
                    return True
                else:
                    status.error_count += 1
                    status.last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                    self.results.failed_requests += 1
                    return False

        except requests.RequestException as e:
            with self.lock:
                status.error_count += 1
                status.last_error = str(e)
                self.results.failed_requests += 1
            return False

    def get_chain_status(self, node_id: str) -> dict[str, Any] | None:
        """Get blockchain status from a node."""
        status = self.node_status.get(node_id)
        if not status:
            return None

        try:
            # Use correct API endpoint: GET /api/v1/chains
            response = requests.get(
                f"{status.url}/api/v1/chains",
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        return None

    def create_chain(self, node_id: str, chain_name: str = DEFAULT_CHAIN_NAME) -> bool:
        """Create a chain on a node for stress testing."""
        status = self.node_status.get(node_id)
        if not status:
            return False

        try:
            response = requests.post(
                f"{status.url}/api/v1/chains/{chain_name}/create",
                timeout=self.timeout,
            )
            return response.status_code in (200, 201)
        except requests.RequestException:
            return False

    def run_flood_test(
        self,
        duration: float = 30.0,
        events_per_second: int = 10,
        workers: int = 4,
    ) -> StressTestResult:
        """
        Run flood test - send many events in parallel.

        Args:
            duration: Test duration in seconds.
            events_per_second: Target events per second.
            workers: Number of parallel workers.

        Returns:
            StressTestResult with metrics.
        """
        logger.info(
            "Starting flood test: duration=%ss, eps=%s, workers=%s",
            duration, events_per_second, workers
        )

        self.results = StressTestResult()
        start_time = time.time()
        event_interval = 1.0 / events_per_second

        def send_events():
            local_count = 0
            while time.time() - start_time < duration:
                # Pick a random healthy node
                healthy = [
                    nid for nid, s in self.node_status.items()
                    if s.is_healthy
                ]
                if not healthy:
                    time.sleep(0.1)
                    continue

                node_id = random.choice(healthy)
                event = self.generate_event()
                self.submit_event(node_id, event)
                local_count += 1

                with self.lock:
                    self.results.total_requests += 1

                time.sleep(event_interval / workers)

            return local_count

        # Run with thread pool
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(send_events) for _ in range(workers)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error("Worker error: %s", e)

        # Calculate averages
        all_times = []
        for status in self.node_status.values():
            all_times.extend(status.response_times)
            self.results.nodes[status.node_id] = status

        if all_times:
            self.results.avg_response_time = sum(all_times) / len(all_times)

        return self.results

    def print_results(self) -> None:
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("  STRESS TEST RESULTS")
        print("=" * 60)
        print(f"Total Requests:     {self.results.total_requests}")
        print(f"Successful:         {self.results.successful_requests}")
        print(f"Failed:             {self.results.failed_requests}")
        print(f"Avg Response Time:  {self.results.avg_response_time*1000:.2f}ms")
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


def run_real_stress_test(
    duration: int = TEST_DURATION,
    events_per_second: int = 20,
    workers: int = 4,
) -> StressTestResult:
    """
    Run real stress test against HieraChain nodes.

    Args:
        duration: Test duration in seconds.
        events_per_second: Target events per second.
        workers: Number of parallel workers.

    Returns:
        StressTestResult with metrics.
    """
    client = RealStressClient()

    # Wait for nodes to be healthy
    logger.info("Waiting for nodes to become healthy...")
    if not client.wait_for_nodes(timeout=60):
        logger.warning("Not all nodes are healthy, proceeding anyway")

    # Create chain on healthy nodes for stress testing
    logger.info("Creating stress test chain on healthy nodes...")
    chain_created = False
    for node_id, node_status in client.node_status.items():
        if node_status.is_healthy:
            if client.create_chain(node_id, DEFAULT_CHAIN_NAME):
                logger.info("Chain created on %s", node_id)
                chain_created = True
            else:
                logger.warning("Failed to create chain on %s", node_id)
    
    if not chain_created:
        logger.error("Could not create chain on any node!")

    # Run test
    results = client.run_flood_test(
        duration=duration,
        events_per_second=events_per_second,
        workers=workers,
    )

    client.print_results()
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    results = run_real_stress_test(
        duration=30,
        events_per_second=10,
        workers=4,
    )

    print(f"\nTest completed: {results.successful_requests}/{results.total_requests} successful")
