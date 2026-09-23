"""
Real Network Stress Tests.

These tests send actual HTTP requests to running HieraChain nodes.
Requires Docker containers to be running with the API server.
"""

import pytest
import logging

from docker.stress.real_stress_client import (
    RealStressClient,
    run_real_stress_test,
    REAL_REQUESTS,
    generate_event,
)

logger = logging.getLogger(__name__)


# Skip tests if REAL_REQUESTS is not enabled
pytestmark = pytest.mark.skipif(
    not REAL_REQUESTS,
    reason="Real network tests disabled (set REAL_REQUESTS=true)"
)


class TestRealNetworkStress:
    """Real network stress tests against running HieraChain nodes."""

    def test_node_health_check(self):
        """Test that all nodes are healthy."""
        client = RealStressClient()

        # Try to connect to nodes
        health = client.check_all_nodes()

        assert health and all(health.values()), f"Not all configured nodes are healthy: {health}"

    def test_wait_for_nodes(self):
        """Test waiting for nodes to become healthy."""
        client = RealStressClient()

        # Short timeout for test
        result = client.wait_for_nodes(timeout=10)

        assert result, "Configured Docker nodes did not become healthy"

    @pytest.mark.stress
    def test_light_stress(self):
        """Light stress test - 10 seconds, 5 events/sec."""
        results = run_real_stress_test(
            duration=10,
            events_per_second=5,
            workers=2,
        )

        assert results.total_requests > 0
        assert results.successful_requests + results.failed_requests == results.total_requests
        assert results.successful_requests > 0

        print(f"\n=== Light Stress Test Results ===")
        print(f"Total Requests: {results.total_requests}")
        print(f"Successful: {results.successful_requests}")
        print(f"Failed: {results.failed_requests}")
        print(f"Avg Response Time: {results.avg_response_time*1000:.2f}ms")

        success_rate = results.successful_requests / results.total_requests
        print(f"Success Rate: {success_rate*100:.1f}%")

    @pytest.mark.stress
    def test_medium_stress(self):
        """Medium stress test - 30 seconds, 20 events/sec."""
        results = run_real_stress_test(
            duration=30,
            events_per_second=20,
            workers=4,
        )

        assert results.total_requests > 0
        assert results.successful_requests + results.failed_requests == results.total_requests
        assert results.successful_requests > 0

        print(f"\n=== Medium Stress Test Results ===")
        print(f"Total Requests: {results.total_requests}")
        print(f"Successful: {results.successful_requests}")
        print(f"Avg Response Time: {results.avg_response_time*1000:.2f}ms")

        success_rate = results.successful_requests / results.total_requests
        print(f"Success Rate: {success_rate*100:.1f}%")

    @pytest.mark.stress
    def test_heavy_stress(self):
        """Heavy stress test - 60 seconds, 50 events/sec."""
        results = run_real_stress_test(
            duration=60,
            events_per_second=50,
            workers=8,
        )

        assert results.total_requests > 0
        assert results.successful_requests + results.failed_requests == results.total_requests
        assert results.successful_requests > 0

        print(f"\n=== Heavy Stress Test Results ===")
        print(f"Total Requests: {results.total_requests}")
        print(f"Successful: {results.successful_requests}")
        print(f"Failed: {results.failed_requests}")
        print(f"Avg Response Time: {results.avg_response_time*1000:.2f}ms")

        success_rate = results.successful_requests / results.total_requests
        print(f"Success Rate: {success_rate*100:.1f}%")
        assert success_rate >= 0.05, f"Too many failures: {success_rate*100:.1f}%"


class TestEventSubmission:
    """Test event submission to actual nodes."""

    def test_generate_event(self):
        """Test event generation."""
        client = RealStressClient()
        event = generate_event()

        # Match EventRequest schema from hierachain.api.ledger.schemas
        assert "entity_id" in event
        assert "event_type" in event
        assert "details" in event
        assert "data" in event["details"]

    @pytest.mark.stress
    def test_submit_single_event(self):
        """Test submitting a single event."""
        client = RealStressClient()

        # Check if nodes are available
        assert client.wait_for_nodes(timeout=60), "Configured Docker nodes did not become healthy"

        # Find a healthy node
        healthy = [
            nid for nid, s in client.node_status.items()
            if s.is_healthy
        ]
        assert healthy, "No healthy Docker node to receive the event"

        node_id = healthy[0]
        event = generate_event()

        result = client.submit_event(node_id, event)
        print(f"\nEvent submitted to {node_id}: {result}")
        assert result, f"Live event submission failed on {node_id}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v", "-s"])
