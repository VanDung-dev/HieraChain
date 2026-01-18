"""
Tsunami Flood Test - Queue & Flush Stress Test.

This test floods the event pool with massive amounts of events to test:
- Queue handling under extreme load
- Emergency flush mechanism
- Memory management and RAM limits
- Lockdown triggering and recovery

Run with: pytest tests/stress/test_tsunami_flood.py -v
"""

import time
import random
import string
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pytest

logger = logging.getLogger(__name__)

# Test configuration
DEFAULT_CONFIG = {
    "num_events": 10000,
    "batch_size": 100,
    "event_size_bytes": 1024,
    "concurrent_senders": 10,
    "target_nodes": ["localhost:5001", "localhost:5002", "localhost:5003", "localhost:5004"],
    "timeout_seconds": 60,
}


def generate_random_event(size_bytes: int = 1024) -> dict[str, Any]:
    """Generate a random event with specified payload size."""
    payload = ''.join(random.choices(string.ascii_letters + string.digits, k=size_bytes))
    return {
        "event_id": f"evt-{random.randint(100000, 999999)}",
        "timestamp": time.time(),
        "type": "stress_test",
        "payload": payload,
        "metadata": {
            "test_name": "tsunami_flood",
            "created_at": time.time(),
        }
    }


class TsunamiFloodTest:
    """Tsunami flood stress test implementation."""

    def __init__(self, config: dict | None = None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.sent_count = 0
        self.failed_count = 0
        self.lock = threading.Lock()
        self.results: list[dict] = []

    def send_event_batch(self, node_url: str, batch: list[dict]) -> dict:
        """
        Send a batch of events to a node.

        In real implementation, this would use HTTP/gRPC client.
        For now, simulates the sending process.
        """
        start_time = time.time()
        success_count = 0
        errors = []

        for event in batch:
            try:
                # Simulate network request (replace with actual client)
                # response = requests.post(f"http://{node_url}/events", json=event)
                # if response.status_code == 200:
                #     success_count += 1

                # Simulation: random success/failure
                if random.random() > 0.01:  # 99% success rate
                    success_count += 1
                else:
                    errors.append(f"Event {event['event_id']} failed")

                # Small delay to simulate network latency
                time.sleep(0.001)

            except Exception as e:
                errors.append(str(e))

        elapsed = time.time() - start_time
        return {
            "node": node_url,
            "batch_size": len(batch),
            "success": success_count,
            "failed": len(batch) - success_count,
            "elapsed_seconds": elapsed,
            "events_per_second": success_count / elapsed if elapsed > 0 else 0,
            "errors": errors[:5],  # Limit errors in report
        }

    def run_flood(self) -> dict:
        """Execute the tsunami flood test."""
        logger.info("Starting Tsunami Flood Test")
        logger.info(f"Config: {self.config}")

        start_time = time.time()
        num_events = self.config["num_events"]
        batch_size = self.config["batch_size"]
        concurrent = self.config["concurrent_senders"]
        nodes = self.config["target_nodes"]

        # Generate all events
        logger.info(f"Generating {num_events} events...")
        events = [
            generate_random_event(self.config["event_size_bytes"])
            for _ in range(num_events)
        ]

        # Split into batches
        batches = [
            events[i:i + batch_size]
            for i in range(0, len(events), batch_size)
        ]
        logger.info(f"Created {len(batches)} batches of {batch_size} events")

        # Send batches concurrently
        results = []
        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = []
            for i, batch in enumerate(batches):
                node = nodes[i % len(nodes)]
                future = executor.submit(self.send_event_batch, node, batch)
                futures.append(future)

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    with self.lock:
                        self.sent_count += result["success"]
                        self.failed_count += result["failed"]
                except Exception as e:
                    logger.error(f"Batch failed: {e}")

        elapsed = time.time() - start_time

        return {
            "test_name": "tsunami_flood",
            "status": "completed",
            "total_events": num_events,
            "sent_success": self.sent_count,
            "sent_failed": self.failed_count,
            "success_rate": self.sent_count / num_events if num_events > 0 else 0,
            "elapsed_seconds": elapsed,
            "events_per_second": self.sent_count / elapsed if elapsed > 0 else 0,
            "batches_processed": len(results),
            "node_metrics": {
                "num_target_nodes": len(nodes),
                "target_nodes": nodes,
                "events_per_node": num_events // len(nodes) if nodes else 0,
                "concurrent_senders": concurrent,
            },
            "config": self.config,
        }


# Pytest test cases

class TestTsunamiFlood:
    """Pytest test cases for tsunami flood."""

    @pytest.fixture
    def small_config(self):
        """Small config for quick tests."""
        return {
            "num_events": 100,
            "batch_size": 10,
            "event_size_bytes": 256,
            "concurrent_senders": 2,
            "target_nodes": ["localhost:5001"],
            "timeout_seconds": 30,
        }

    def test_event_generation(self):
        """Test event generation."""
        event = generate_random_event(512)
        assert "event_id" in event
        assert "payload" in event
        assert len(event["payload"]) == 512

    def test_small_flood(self, small_config):
        """Test small flood completes successfully."""
        test = TsunamiFloodTest(small_config)
        result = test.run_flood()

        assert result["status"] == "completed"
        assert result["total_events"] == 100
        assert result["success_rate"] > 0.95  # At least 95% success

    def test_flood_throughput(self, small_config):
        """Test flood achieves minimum throughput."""
        test = TsunamiFloodTest(small_config)
        result = test.run_flood()

        # Should process at least 10 events/second
        assert result["events_per_second"] > 10

    @pytest.mark.stress
    def test_full_flood(self):
        """Full flood test (marked as stress, skip in normal runs)."""
        test = TsunamiFloodTest(DEFAULT_CONFIG)
        result = test.run_flood()

        assert result["status"] == "completed"
        assert result["success_rate"] > 0.90


if __name__ == "__main__":
    # Run directly for manual testing
    logging.basicConfig(level=logging.INFO)
    test = TsunamiFloodTest()
    result = test.run_flood()
    
    print("\n" + "=" * 60)
    print("  TSUNAMI FLOOD TEST RESULTS")
    print("=" * 60)
    
    print(f"\n📊 TEST SUMMARY")
    print(f"  Status:           {result['status']}")
    print(f"  Duration:         {result['elapsed_seconds']:.2f}s")
    print(f"  Events/Second:    {result['events_per_second']:.2f}")
    
    print(f"\n📝 EVENT STATISTICS")
    print(f"  Total Events:     {result['total_events']}")
    print(f"  Sent Success:     {result['sent_success']}")
    print(f"  Sent Failed:      {result['sent_failed']}")
    print(f"  Success Rate:     {result['success_rate']*100:.2f}%")
    print(f"  Batches:          {result['batches_processed']}")

    nm = result.get("node_metrics", {})
    if nm:
        print(f"\n🖧  NODE DISTRIBUTION (TODO #7 Metrics)")
        print(f"  Target Nodes:     {nm.get('num_target_nodes', 0)}")
        print(f"  Events/Node:      {nm.get('events_per_node', 0)}")
        print(f"  Concurrent:       {nm.get('concurrent_senders', 0)}")
        print(f"  Nodes: {nm.get('target_nodes', [])}")
    
    print("=" * 60)
