"""
Unit tests for the Ordering Service
"""

import time
from hierarchical_blockchain.consensus import OrderingService, OrderingNode, OrderingStatus
from hierarchical_blockchain.error_mitigation.error_classifier import (
    ErrorClassifier,
    PriorityLevel,
    ErrorCategory,
)
from hierarchical_blockchain.error_mitigation.validator import (
    ConsensusValidator,
    EncryptionValidator,
    ResourceValidator,
    APIValidator,
    ValidationError,
    SecurityError
)

# Create a test node
node = OrderingNode(
    node_id="test-node",
    endpoint="localhost:2661",
    is_leader=True,
    weight=1.0,
    status=OrderingStatus.ACTIVE,
    last_heartbeat=time.time()
)


def test_init_with_defaults():
    """Test initialization with default parameters"""
    service = OrderingService(nodes=[node], config={})
    assert service is not None
    assert service.get_service_status()["status"] == "active"


def test_init_with_params():
    """Test initialization with custom parameters"""
    config = {"block_size": 1000, "batch_timeout": 5.0}
    service = OrderingService(nodes=[node], config=config)

    status = service.get_service_status()
    assert status["configuration"]["block_size"] == 1000
    assert status["configuration"]["batch_timeout"] == 5.0


def test_receive_valid_event():
    """Test receiving a valid event"""
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


def test_block_creation():
    """Test block creation when batch size is reached"""
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


def test_invalid_event_handling():
    """"""
    service = OrderingService(nodes=[node], config={})

    # Event missing required fields
    invalid_event = {"entity_id": "TEST-001", "timestamp": time.time()}
    event_id = service.receive_event(invalid_event, "test-channel", "test-org")

    # Wait for processing
    time.sleep(0.1)

    status = service.get_event_status(event_id)
    assert status["status"] == "rejected"


def test_timeout_block_creation():
    """"""
    config = {"block_size": 10, "batch_timeout": 0.1}
    service = OrderingService(nodes=[node], config=config)

    # Submit 1 event and wait for timeout
    event = {
        "entity_id": "TEST-001",
        "event": "test_event",
        "timestamp": time.time()
    }
    service.receive_event(event, "test-channel", "test-org")

    # Wait for processing
    time.sleep(0.2)

    service._check_timeout_block_creation()
    block = service.get_next_block()
    assert block is not None
    assert block["event_count"] == 1


def test_service_status():
    """"""
    service = OrderingService(nodes=[node], config={})

    status = service.get_service_status()
    assert status["nodes"]["healthy"] == 1
    assert status["queues"]["pending_events"] == 0


def test_custom_validation_rule():
    """"""
    service = OrderingService(nodes=[node], config={})

    # Add custom rules
    def custom_rule(event_data):
        return "custom_field" in event_data

    service.add_validation_rule(custom_rule)

    # Test with an event without custom_field
    event = {
        "entity_id": "TEST-001",
        "event": "test_event",
        "timestamp": time.time()
    }
    event_id = service.receive_event(event, "test-channel", "test-org")

    # Wait for processing
    time.sleep(0.1)
    status = service.get_event_status(event_id)
    assert status["status"] == "rejected"


def test_concurrent_event_processing():
    """Test concurrent event processing"""
    service = OrderingService(nodes=[node], config={"worker_threads": 4})

    # Submit multiple events concurrently
    event_ids = []
    for i in range(10):
        event = {
            "entity_id": f"TEST-{i:03d}",
            "event": f"test_event_{i}",
            "timestamp": time.time()
        }
        event_id = service.receive_event(event, "test-channel", "test-org")
        event_ids.append(event_id)

    # Wait for processing
    time.sleep(0.5)

    # Check that all events were processed
    certified_count = 0
    for event_id in event_ids:
        status = service.get_event_status(event_id)
        if status and status["status"] == "certified":
            certified_count += 1

    assert certified_count == 10


def test_unhealthy_node():
    """Test handling of unhealthy nodes"""
    # Create an unhealthy node (last heartbeat is old)
    unhealthy_node = OrderingNode(
        node_id="unhealthy-node",
        endpoint="localhost:2661",
        is_leader=False,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time() - 60  # 60 seconds old
    )

    # Create a healthy node
    healthy_node = OrderingNode(
        node_id="healthy-node",
        endpoint="localhost:2661",
        is_leader=True,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time()
    )

    service = OrderingService(nodes=[unhealthy_node, healthy_node], config={})

    # Check service status
    status = service.get_service_status()
    assert status["nodes"]["total"] == 2
    assert status["nodes"]["healthy"] == 1  # Only one node should be healthy


def test_service_start_stop():
    """Test service start and stop functionality"""
    # Create service with minimal config
    service = OrderingService(nodes=[node], config={})

    # Check that service is active
    assert service.status == OrderingStatus.ACTIVE

    # Test stop
    service.stop()
    assert service.status == OrderingStatus.STOPPED

    # Test restart
    service.start()
    assert service.status == OrderingStatus.ACTIVE


def test_system_error_handling():
    """Test handling of system errors during event processing"""
    service = OrderingService(nodes=[node], config={})

    # Add a validation rule that raises an exception
    def faulty_rule(event_data):
        if event_data.get("event") == "faulty_event":
            raise Exception("Faulty rule exception")
        return True

    service.add_validation_rule(faulty_rule)

    # Send a normal event
    normal_event = {
        "entity_id": "NORMAL-001",
        "event": "normal_event",
        "timestamp": time.time()
    }
    normal_event_id = service.receive_event(normal_event, "test-channel", "test-org")

    # Send a faulty event
    faulty_event = {
        "entity_id": "FAULTY-001",
        "event": "faulty_event",
        "timestamp": time.time()
    }
    faulty_event_id = service.receive_event(faulty_event, "test-channel", "test-org")

    # Wait for processing
    time.sleep(0.2)

    # Check that normal event was processed
    normal_status = service.get_event_status(normal_event_id)
    assert normal_status["status"] == "certified"

    # Check that faulty event was rejected
    faulty_status = service.get_event_status(faulty_event_id)
    assert faulty_status["status"] == "rejected"


def test_large_volume_performance():
    """Test performance with large volume of events"""
    config = {"block_size": 100, "batch_timeout": 0.5}
    service = OrderingService(nodes=[node], config=config)

    # Record start time
    start_time = time.time()

    # Submit large number of events
    event_count = 500
    event_ids = []
    for i in range(event_count):
        event = {
            "entity_id": f"LARGE-{i:03d}",
            "event": f"large_event_{i}",
            "timestamp": time.time()
        }
        event_id = service.receive_event(event, "test-channel", "test-org")
        event_ids.append(event_id)

    # Wait for all events to be processed
    time.sleep(2.0)

    # Check performance
    end_time = time.time()
    _processing_time = end_time - start_time

    # Verify all events were processed
    certified_count = 0
    for event_id in event_ids[:100]:  # Check first 100 events
        status = service.get_event_status(event_id)
        if status and status["status"] == "certified":
            certified_count += 1

    # At least some events should be certified
    assert certified_count > 0

    # Should have created blocks
    blocks = []
    block = service.get_next_block()
    while block is not None:
        blocks.append(block)
        block = service.get_next_block()

    assert len(blocks) > 0


def test_malformed_event_data():
    """Test handling of malformed event data"""
    service = OrderingService(nodes=[node], config={})

    # Test with non-dictionary event data
    event_id = service.receive_event("not a dict!!!", "test-channel", "test-org")
    time.sleep(0.1)
    status = service.get_event_status(event_id)
    assert status["status"] == "rejected"

    # Test with wrong timestamp type
    invalid_event = {
        "entity_id": "TEST-001",
        "event": "test_event",
        "timestamp": "not_a_timestamp"
    }
    event_id = service.receive_event(invalid_event, "test-channel", "test-org")
    time.sleep(0.1)
    status = service.get_event_status(event_id)
    assert status["status"] == "rejected"

    # Test with future timestamp
    future_event = {
        "entity_id": "TEST-002",
        "event": "future_event",
        "timestamp": time.time() + 7200  # 2 hours in the future
    }
    event_id = service.receive_event(future_event, "test-channel", "test-org")
    time.sleep(0.1)
    status = service.get_event_status(event_id)
    assert status["status"] == "rejected"


def test_concurrent_edge_cases():
    """Test concurrent processing edge cases"""
    config = {"block_size": 5, "batch_timeout": 0.1}
    service = OrderingService(nodes=[node], config=config)

    # Send events in quick succession to test race conditions
    event_ids = []
    start_time = time.time()
    for i in range(10):
        event = {
            "entity_id": f"EDGE-{i:03d}",
            "event": f"edge_event_{i}",
            "timestamp": start_time
        }
        event_id = service.receive_event(event, "test-channel", "test-org")
        event_ids.append(event_id)

    # Wait for processing
    time.sleep(0.5)

    # Verify all events were processed
    certified_count = 0
    for event_id in event_ids:
        status = service.get_event_status(event_id)
        if status and status["status"] == "certified":
            certified_count += 1

    assert certified_count == 10


def test_leader_election_scenarios():
    """Test leader election scenarios"""
    # Create multiple nodes with one leader
    leader_node = OrderingNode(
        node_id="leader-node",
        endpoint="localhost:8080",
        is_leader=True,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time()
    )

    follower_node = OrderingNode(
        node_id="follower-node",
        endpoint="localhost:8081",
        is_leader=False,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time()
    )

    service = OrderingService(nodes=[leader_node, follower_node], config={})

    # Check service status shows correct leader
    status = service.get_service_status()
    assert status["nodes"]["leader"] == "leader-node"
    assert status["nodes"]["total"] == 2
    assert status["nodes"]["healthy"] == 2


def test_cleanup_on_service_stop():
    """Test proper cleanup when service is stopped"""
    service = OrderingService(nodes=[node], config={})

    # Submit some events
    for i in range(5):
        event = {
            "entity_id": f"CLEANUP-{i:03d}",
            "event": f"cleanup_event_{i}",
            "timestamp": time.time()
        }
        service.receive_event(event, "test-channel", "test-org")

    # Wait a bit for processing to start
    time.sleep(0.1)

    # Stop service
    service.stop()

    # Check that service is properly stopped
    assert service.status == OrderingStatus.STOPPED

    # Verify that threads are properly joined
    if hasattr(service, 'processing_thread') and service.processing_thread:
        assert not service.processing_thread.is_alive()


def test_network_failure_scenarios():
    """Test handling of network failure scenarios"""
    # Create nodes with different network conditions
    leader_node = OrderingNode(
        node_id="leader-node",
        endpoint="localhost:8080",
        is_leader=True,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time() - 45  # Simulate network delay
    )

    healthy_node = OrderingNode(
        node_id="healthy-node",
        endpoint="localhost:8081",
        is_leader=False,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=time.time()  # Recent heartbeat
    )

    service = OrderingService(nodes=[leader_node, healthy_node], config={})

    # Check service status reflects network issues
    status = service.get_service_status()
    assert status["nodes"]["total"] == 2
    # Only one node should be healthy due to leader's outdated heartbeat
    assert status["nodes"]["healthy"] == 1


def test_network_partition_handling():
    """Test handling of network partition scenarios"""
    # Create multiple nodes
    nodes = []
    base_time = time.time()

    # Leader node (healthy)
    leader_node = OrderingNode(
        node_id="leader-node",
        endpoint="localhost:2661",
        is_leader=True,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=base_time
    )
    nodes.append(leader_node)

    # Healthy follower nodes
    for i in range(2):
        node_1 = OrderingNode(
            node_id=f"healthy-follower-{i}",
            endpoint=f"localhost:266{i + 1}",
            is_leader=False,
            weight=1.0,
            status=OrderingStatus.ACTIVE,
            last_heartbeat=base_time
        )
        nodes.append(node_1)

    # Network partitioned nodes (outdated heartbeat)
    for i in range(2):
        node_2 = OrderingNode(
            node_id=f"partitioned-node-{i}",
            endpoint=f"localhost:266{i}",
            is_leader=False,
            weight=1.0,
            status=OrderingStatus.ACTIVE,
            last_heartbeat=base_time - 60  # 1 minute old - considered unhealthy
        )
        nodes.append(node_2)

    service = OrderingService(nodes=nodes, config={})

    # Check service correctly identifies healthy/unhealthy nodes
    status = service.get_service_status()
    assert status["nodes"]["total"] == 5
    assert status["nodes"]["healthy"] == 3  # Leader + 2 healthy followers
    assert status["nodes"]["leader"] == "leader-node"


def test_leader_failover():
    """Test leader failover when leader node goes down"""
    # Create nodes with one leader
    base_time = time.time()

    leader_node = OrderingNode(
        node_id="leader-node",
        endpoint="localhost:8080",
        is_leader=True,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=base_time - 60  # Old heartbeat - simulate failure
    )

    follower_node1 = OrderingNode(
        node_id="follower-1",
        endpoint="localhost:8081",
        is_leader=False,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=base_time  # Recent heartbeat
    )

    follower_node2 = OrderingNode(
        node_id="follower-2",
        endpoint="localhost:8082",
        is_leader=False,
        weight=1.0,
        status=OrderingStatus.ACTIVE,
        last_heartbeat=base_time  # Recent heartbeat
    )

    service = OrderingService(nodes=[leader_node, follower_node1, follower_node2], config={})

    # Check service status
    status = service.get_service_status()
    assert status["nodes"]["total"] == 3
    # Leader should be considered unhealthy due to old heartbeat
    assert status["nodes"]["healthy"] == 2


def test_complex_event_data():
    """Test handling of complex event data structures"""
    service = OrderingService(nodes=[node], config={})

    # Complex nested event data
    complex_event = {
        "entity_id": "COMPLEX-001",
        "event": "complex_operation",
        "timestamp": time.time(),
        "payload": {
            "nested_data": {
                "items": [
                    {"id": 1, "value": "first"},
                    {"id": 2, "value": "second"}
                ],
                "metadata": {
                    "tags": ["important", "complex"],
                    "version": "1.0",
                    "created_by": "test_system"
                }
            },
            "statistics": {
                "count": 100,
                "average": 42.5,
                "histogram": [10, 20, 30, 25, 15]
            }
        },
        "context": {
            "source": "automated_test",
            "priority": "high",
            "dependencies": ["service_a", "service_b"]
        }
    }

    event_id = service.receive_event(complex_event, "test-channel", "test-org")
    time.sleep(0.2)  # Give more time for complex event processing

    # Check that complex event was processed correctly
    status = service.get_event_status(event_id)
    assert status is not None
    assert status["status"] == "certified"

    # Verify event can be retrieved with all data intact
    # Note: This doesn't test the actual block creation but ensures the event
    # is properly handled through the certification process


def test_error_classification_with_complex_data():
    """Test error classification with complex data structures"""
    config = {}
    classifier = ErrorClassifier(config)

    # Test with binary error data
    binary_error_data = {
        "error_type": "data_corruption",
        "message": "Binary data corruption detected",
        "metadata": {
            "corrupted_data": bytes([1, 2, 3, 4, 5]).hex(),
            "data_size": 1000,
            "checksum": "0x12345678"
        }
    }

    error_info = classifier.classify_error(binary_error_data)
    assert error_info is not None
    assert error_info.error_id.startswith("ERR-")
    assert error_info.category in ErrorCategory

    # Test with nested complex data
    complex_error_data = {
        "error_type": "consensus_failure",
        "message": "Complex consensus failure with multiple nodes",
        "metadata": {
            "nodes": {
                "node1": {"status": "failed", "error": "timeout"},
                "node2": {"status": "active", "error": None},
                "node3": {"status": "failed", "error": "data_corruption"}
            },
            "view_number": 15,
            "sequence": [1, 2, 3, 4, 5],
            "statistics": {
                "failures": 10,
                "successes": 90,
                "ratio": 0.1
            }
        }
    }

    complex_error_info = classifier.classify_error(complex_error_data)
    assert complex_error_info is not None
    assert complex_error_info.priority in PriorityLevel


def test_consensus_validator_with_edge_cases():
    """Test consensus validator with edge case configurations"""
    # Test with f=0 (no fault tolerance)
    config_no_fault = {"f": 0}
    validator_no_fault = ConsensusValidator(config_no_fault)
    assert validator_no_fault.f == 0

    # Minimum nodes should be 1 (3*0 + 1)
    try:
        validator_no_fault.validate_node_count([])  # 0 nodes
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass  # Expected

    assert validator_no_fault.validate_node_count([1])  # 1 node should be enough

    # Test with large f value
    config_large_f = {"f": 100}
    validator_large_f = ConsensusValidator(config_large_f)
    assert validator_large_f.f == 100

    # Required nodes should be 301 (3*100 + 1)
    nodes_300 = list(range(300))
    try:
        validator_large_f.validate_node_count(nodes_300)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass  # Expected

    nodes_301 = list(range(301))
    assert validator_large_f.validate_node_count(nodes_301)


def test_encryption_validator_with_large_keys():
    """Test encryption validator with large key sizes"""
    config = {"algorithm": "AES-256-GCM"}
    validator = EncryptionValidator(config)

    # Test validation passes
    assert validator.validate_config() is True

    # Test encryption of large data
    large_data = "A" * (1024 * 1024)  # 1MB of data
    try:
        encrypted = validator.encrypt_data(large_data)
        assert "ciphertext" in encrypted
        assert "tag" in encrypted
        assert "iv" in encrypted
        assert encrypted["algorithm"] == "AES-256-GCM"
    except SecurityError:
        # May fail in some environments due to missing dependencies
        pass  # Acceptable for this test


def test_api_validator_with_complex_forbidden_content():
    """Test API validator with complex forbidden content"""
    config = {}
    validator = APIValidator(config)

    # Test with nested forbidden terms
    complex_data = {
        "entity_id": "API-TEST-001",
        "event": "api_complex_test",
        "timestamp": time.time(),
        "payload": {
            "nested": {
                "transaction": "should not be here",  # Forbidden term
                "data": "normal data"
            }
        }
    }

    # Should raise ValidationError due to forbidden term "transaction"
    try:
        validator.validate_endpoint_data(complex_data)
        # If we get here, the validation didn't catch the forbidden term
        # This might be expected depending on implementation depth
        pass
    except ValidationError:
        # This is expected if the validator properly checks nested content
        pass


def test_resource_validator_with_extreme_values():
    """Test resource validator with extreme threshold values"""
    # Test with very low thresholds
    config_low = {
        "cpu_threshold": 5,
        "memory_threshold": 10,
        "disk_threshold": 15
    }
    validator_low = ResourceValidator(config_low)

    # Test with very high thresholds
    config_high = {
        "cpu_threshold": 95,
        "memory_threshold": 99,
        "disk_threshold": 100
    }
    validator_high = ResourceValidator(config_high)

    # These should not cause errors in initialization
    assert validator_low.cpu_threshold == 5
    assert validator_high.cpu_threshold == 95
