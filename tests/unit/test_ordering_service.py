"""
Unit tests for the Ordering Service
"""

import time
from hierarchical_blockchain.consensus import OrderingService, OrderingNode, OrderingStatus


class TestOrderingService:
    """Test cases for OrderingService"""

    def test_init_with_defaults(self):
        """Test initialization with default parameters"""
        node = OrderingNode(
            node_id="test-node",
            endpoint="localhost:8080",
            is_leader=True,
            weight=1.0,
            status=OrderingStatus.ACTIVE,
            last_heartbeat=time.time()
        )
        service = OrderingService(nodes=[node], config={})
        assert service is not None
        assert service.get_service_status()["status"] == "active"

    def test_init_with_params(self):
        """Test initialization with custom parameters"""
        node = OrderingNode(
            node_id="test-node",
            endpoint="localhost:8080",
            is_leader=True,
            weight=1.0,
            status=OrderingStatus.ACTIVE,
            last_heartbeat=time.time()
        )
        config = {"block_size": 1000, "batch_timeout": 5.0}
        service = OrderingService(nodes=[node], config=config)

        status = service.get_service_status()
        assert status["configuration"]["block_size"] == 1000
        assert status["configuration"]["batch_timeout"] == 5.0

    def test_receive_valid_event(self):
        """Test receiving a valid event"""
        node = OrderingNode(
            node_id="test-node",
            endpoint="localhost:8080",
            is_leader=True,
            weight=1.0,
            status=OrderingStatus.ACTIVE,
            last_heartbeat=time.time()
        )
        service = OrderingService(nodes=[node], config={})
        event = {
            "entity_id": "TEST-001",
            "event": "test_event",
            "timestamp": time.time()
        }

        event_id = service.receive_event(event, "test-channel", "test-org")
        assert event_id is not None

        # Check event status
        status = service.get_event_status(event_id)
        assert status is not None
        assert status["status"] in ["pending", "certified"]

    def test_block_creation(self):
        """Test block creation when batch size is reached"""
        node = OrderingNode(
            node_id="test-node",
            endpoint="localhost:2661",
            is_leader=True,
            weight=1.0,
            status=OrderingStatus.ACTIVE,
            last_heartbeat=time.time()
        )
        config = {"block_size": 3, "batch_timeout": 0.1}
        service = OrderingService(nodes=[node], config=config)

        # Add events to reach batch size
        event_ids = []
        for i in range(3):
            event = {
                "entity_id": f"TEST-{i:03d}",
                "event": "test_event",
                "timestamp": time.time()
            }
            event_id = service.receive_event(event, "test-channel", "test-org")
            event_ids.append(event_id)

        # Wait a bit for processing
        time.sleep(0.2)

        # Should have created a block and added to commit queue
        block = service.get_next_block()
        assert block is not None
        assert block["event_count"] == 3
