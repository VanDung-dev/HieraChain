"""
Unit tests for the Ordering Service
"""

import time
from hierarchical.ordering.ordering_service import OrderingService


class TestOrderingService:
    """Test cases for OrderingService"""
    
    def test_init_with_defaults(self):
        """Test initialization with default parameters"""
        service = OrderingService()
        assert service is not None
        assert service.config["block_size"] == 500
        assert service.config["batch_size"] == 100
        assert service.pool_size() == 0
    
    def test_init_with_params(self):
        """Test initialization with custom parameters"""
        config = {"block_size": 1000, "batch_size": 50}
        service = OrderingService(config=config)
        
        assert service.config["block_size"] == 1000
        assert service.config["batch_size"] == 50
    
    def test_receive_valid_event(self):
        """Test receiving a valid event"""
        service = OrderingService()
        event = {
            "entity_id": "TEST-001",
            "event": "test_event",
            "timestamp": time.time()
        }
        
        service.receive_event(event)
        assert service.pool_size() == 1
    
    def test_receive_invalid_event(self):
        """Test receiving an invalid event"""
        service = OrderingService()
        
        # Event missing required fields
        invalid_event = {
            "event": "test_event",
            "timestamp": time.time()
        }
        
        service.receive_event(invalid_event)
        assert service.pool_size() == 0
    
    def test_block_creation(self):
        """Test block creation when batch size is reached"""
        config = {"block_size": 10, "batch_size": 5}
        service = OrderingService(config=config)
        
        # Add events to reach batch size
        for i in range(5):
            event = {
                "entity_id": f"TEST-{i:03d}",
                "event": "test_event",
                "timestamp": time.time()
            }
            service.receive_event(event)
        
        # Should have created a block and added to commit queue
        assert service.pool_size() == 0
        block = service.get_next_block()
        assert block is not None
        assert len(block.events) == 5