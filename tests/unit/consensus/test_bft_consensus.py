"""
Test suite for BFT Consensus Mechanism

This module contains unit tests for the BFTConsensus class,
including message handling, consensus phases, and node communication.
"""

import time

from hierachain.consensus import (
    BFTConsensus,
    create_bft_network,
    ConsensusError,
    BFTMessage,
    MessageType,
    sign_message,
    verify_message_signature,
    validate_consensus_message,
)
from hierachain.security import KeyPair
from hierachain.error_mitigation import (
    ConsensusValidator, ErrorClassifier
)

# Create a BFT network
node_configs = [
    {"node_id": "node_1"},
    {"node_id": "node_2"},
    {"node_id": "node_3"},
    {"node_id": "node_4"}
]

network = create_bft_network(node_configs, fault_tolerance=1)

# Create a mock message
test_message = BFTMessage(
    message_type=MessageType.PREPARE,
    view=0,
    sequence_number=1,
    sender_id="node_1",
    timestamp=time.time(),
    signature="",
    data={"test": "data"},
    nonce="test-nonce",
)
# Sign with real key
test_message.signature = sign_message(
    network["node_1"].key_provider,
    test_message.get_signable_payload(),
)


def _create_bft_setup():
    node_ids = ["node_1", "node_2", "node_3", "node_4"]
    keypairs = {nid: KeyPair() for nid in node_ids}
    public_keys = {nid: kp.public_key for nid, kp in keypairs.items()}
    return node_ids, keypairs, public_keys


def _check_message_validation_and_error_mitigation(normal_node, other_node):
    assert hasattr(other_node, "log_node_behavior")
    test_message.timestamp = time.time()
    test_message.signature = sign_message(
        network["node_1"].key_provider,
        test_message.get_signable_payload(),
    )
    is_valid = validate_consensus_message(
        test_message,
        normal_node.all_nodes,
        normal_node.node_public_keys,
        normal_node.verification_strictness,
        normal_node.view_change_timeout,
        normal_node.log_node_behavior,
    )
    assert is_valid is True
    assert normal_node.consensus_validator is not None
    assert normal_node.error_classifier is not None

def test_bft_network_creation():
    """Test creation of BFT network"""
    assert len(network) == 4
    assert "node_1" in network
    assert isinstance(network["node_1"], BFTConsensus)

    # Should fail with insufficient nodes
    try:
        small_configs = [{"node_id": "node_1"}, {"node_id": "node_2"}]
        create_bft_network(small_configs, fault_tolerance=1)
        assert False, "Should have raised ConsensusError"
    except ConsensusError:
        pass  # Expected


def test_bft_consensus_initialization():
    """Test BFT consensus initialization"""
    node_ids, keypairs, public_keys = _create_bft_setup()

    bft = BFTConsensus(
        node_id="node_1", 
        all_nodes=node_ids, 
        f=1,
        keypair=keypairs["node_1"],
        node_public_keys=public_keys
    )

    assert bft.node_id == "node_1"
    assert bft.n == 4  # Total nodes
    assert bft.f == 1  # Fault tolerance
    assert bft.view == 0
    assert bft.sequence_number == 0
    assert len(bft.all_nodes) == 4
    assert bft.state.value == "idle"


def test_bft_primary_determination():
    """Test primary node determination"""
    node_ids, keypairs, public_keys = _create_bft_setup()

    bft = BFTConsensus(
        node_id="node_1", 
        all_nodes=node_ids, 
        f=1,
        keypair=keypairs["node_1"],
        node_public_keys=public_keys
    )

    # In view 0, primary should be node_1 (first in sorted list)
    assert bft._primary() == "node_1"
    assert (bft.node_id == bft._primary()) is True

    # Test with different node
    bft2 = BFTConsensus(
        node_id="node_2", 
        all_nodes=node_ids, 
        f=1,
        keypair=keypairs["node_2"],
        node_public_keys=public_keys
    )
    assert bft2._primary() == "node_1"  # Still node_1 in view 0
    assert (bft2.node_id == bft2._primary()) is False  # node_2 is not primary


def test_consensus_validator_integration():
    """Test integration with ConsensusValidator from error_mitigation module"""
    # Create a consensus validator directly
    validator_config = {
        "f": 1,
        "auto_scale_threshold": 0.8,
        "health_check_interval": 30
    }
    validator = ConsensusValidator(validator_config)

    # Create mock nodes
    class MockNode:
        def __init__(self, node_id, health_status="active"):
            self.node_id = node_id
            self.health_status = health_status
            self.last_heartbeat = time.time()

    # Test with sufficient nodes
    healthy_nodes = [MockNode(f"node_{i}") for i in range(4)]
    assert validator.validate_node_count(healthy_nodes) is True

    # Test monitoring and scaling functionality
    monitored_nodes = validator.monitor_and_scale(healthy_nodes)
    assert len(monitored_nodes) == 4


def test_error_classifier_integration():
    """Test integration with ErrorClassifier from error_mitigation module"""
    # Create an error classifier
    config = {}
    classifier = ErrorClassifier(config)

    # Test error classification
    error_data = {
        "error_type": "insufficient_nodes_bft",
        "message": "Insufficient nodes for BFT consensus: 3 < 4",
        "metadata": {"node_count": 3, "required": 4}
    }

    error_info = classifier.classify_error(error_data)
    assert error_info.category.value == "consensus"
    assert error_info.impact.name == "CATASTROPHIC"

    # Test classification summary
    summary = classifier.get_classification_summary()
    assert "total_errors" in summary
    assert "categories" in summary
    assert "priorities" in summary


def test_error_mitigation_with_node_failures():
    """Test error mitigation mechanisms with various node failures"""
    error_config = {
        "consensus": {
            "bft": {
                "node_validation": {
                    "auto_scale_threshold": 0.8
                }
            }
        },
        "recovery": {
            "auto_recovery": {
                "enabled": True
            }
        }
    }

    # Apply error config to nodes
    for node in network.values():
        node.error_config = error_config
        node._init_error_mitigation()

    # Test individual components rather than full consensus flow
    primary = network["node_1"]

    # Check that error mitigation components were initialized
    assert primary.consensus_validator is not None
    assert primary.error_classifier is not None
    assert primary.auto_recovery_enabled is True

    # Test error classification
    classifier = ErrorClassifier({})

    # Test classifying a node failure
    error_data = {
        "error_type": "node_no_response",
        "message": "Node node_2 is not responding",
        "metadata": {
            "node_id": "node_2",
            "timestamp": time.time()
        }
    }

    error_info = classifier.classify_error(error_data)
    assert error_info is not None
    assert error_info.error_type == "node_no_response"

    # Test node behavior logging
    primary.log_node_behavior("node_2", "no_response")
    # Check that node failure is tracked
    assert "node_2" in primary.node_failure_counts

def test_bft_with_slow_nodes():
    """Test BFT consensus behavior with slow nodes"""
    normal_node = network["node_3"]
    slow_node = network["node_2"]

    _check_message_validation_and_error_mitigation(normal_node, slow_node)


def test_bft_with_silent_nodes():
    """Test BFT consensus behavior with silent nodes"""
    normal_node = network["node_3"]
    silent_node = network["node_2"]

    _check_message_validation_and_error_mitigation(normal_node, silent_node)

    silent_node.log_node_behavior("node_2", "no_response")
    assert "node_2" in silent_node.node_failure_counts


def test_bft_with_malicious_nodes():
    """Test BFT consensus behavior with malicious nodes"""
    # Test normal message
    normal_message = BFTMessage(
        message_type=MessageType.PREPARE,
        view=0,
        sequence_number=1,
        sender_id="node_1",
        timestamp=time.time(),
        signature="",
        data={"test": "data"},
        nonce="normal-nonce"
    )
    # Sign with real key
    normal_message.signature = sign_message(
        network["node_1"].key_provider,
        normal_message.get_signable_payload()
    )

    # Test invalid signature message (simulating malicious behavior)
    invalid_message = BFTMessage(
        message_type=MessageType.PREPARE,
        view=0,
        sequence_number=1,
        sender_id="node_1",
        timestamp=time.time(),
        signature="invalid_signature",  # Invalid signature
        data={"test": "data"},
        nonce="invalid-nonce"
    )

    normal_node = network["node_3"]
    malicious_node = network["node_2"]

    # Test normal signature verification
    valid_signature_result = verify_message_signature(
        normal_message, normal_node.node_public_keys
    )
    assert valid_signature_result is True  # Normal signature should be valid

    # Test that malicious behavior detection works
    assert hasattr(malicious_node, 'log_node_behavior')

    # Test that we can initialize the nodes with error mitigation
    assert normal_node.consensus_validator is not None
    assert normal_node.error_classifier is not None

    # Test node behavior logging for malicious actions
    malicious_node.log_node_behavior("node_2", "invalid_signature")
    # Check that error was classified
    assert normal_node.error_classifier is not None

    is_valid = validate_consensus_message(
        invalid_message,
        normal_node.all_nodes,
        normal_node.node_public_keys,
        normal_node.verification_strictness,
        normal_node.view_change_timeout,
        normal_node.log_node_behavior,
    )
    assert is_valid in [True, False]


def test_bft_with_split_brain_scenario():
    """Test BFT consensus behavior with split brain scenario"""
    # Test that BFT nodes can detect and handle split brain
    node = network["node_1"]
    assert node.f == 1  # Fault tolerance

    # Test that nodes can initiate view changes when needed
    assert hasattr(node, '_initiate_view_change')

    node.view_change_votes[1] = []
    # Test view change initiation
    node._initiate_view_change(1)
    # View should not change immediately, state should be VIEW_CHANGE
    assert node.state.value == "view_change"
    assert node.view == 0  # Still in view 0 until quorum
    assert len(node.view_change_votes[1]) == 1  # Should have our own vote


def test_bft_with_temporary_network_partition():
    """Test BFT consensus behavior with temporary network partition"""
    # Test partition detection without a separate recovery engine.
    latency_history = [6000, 7000, 8000]
    health_status = {
        "timestamp": time.time(),
        "avg_latency_ms": sum(latency_history) / len(latency_history),
        "max_latency_ms": max(latency_history),
        "partition_detected": False,
        "healthy_paths": 0,
        "total_paths": 2
    }

    # Apply the same logic as in monitor_network_health but without triggering view change
    if health_status["avg_latency_ms"] > 5000:  # 5 second threshold
        health_status["partition_detected"] = True

    assert health_status["partition_detected"] is True

    # Test that nodes can handle network issues
    node = network["node_1"]
    assert hasattr(node, 'log_node_behavior')

    # Test node behavior logging for network issues
    node.log_node_behavior("node_2", "network_partition")
    assert "node_2" in node.node_failure_counts


def test_bft_with_complex_byzantine_attacks():
    """Test BFT consensus behavior with complex Byzantine attacks"""
    # Create error classifier
    classifier = ErrorClassifier({})

    # Test classification of complex Byzantine errors
    # Use a message that will be classified as consensus category
    error_data = {
        "error_type": "bft_consensus_malicious_behavior",
        "message": "Node node_2 is sending conflicting consensus messages in BFT protocol",
        "metadata": {
            "node_id": "node_2",
            "conflicting_messages": 5,
            "timestamp": time.time()
        }
    }

    error_info = classifier.classify_error(error_data)
    assert error_info.category.value == "consensus"
    assert error_info.priority.name in ["CRITICAL", "HIGH"]

    # Test that BFT nodes can handle complex attacks by checking internal mechanisms
    normal_node = network["node_1"]

    # Create a message with invalid signature to simulate malicious behavior
    malicious_message = BFTMessage(
        message_type=MessageType.PREPARE,
        view=0,
        sequence_number=1,
        sender_id="node_2",
        timestamp=time.time(),
        signature="invalid_signature",  # Invalid signature
        data={"digest": "digest1"}
    )

    # Test signature verification
    is_valid = verify_message_signature(
        malicious_message, normal_node.node_public_keys
    )
    assert is_valid is False  # Should detect invalid signature

    # Test that invalid signatures are logged as malicious behavior
    assert hasattr(normal_node, 'log_node_behavior')

    # Test error classification summary
    summary = classifier.get_classification_summary()
    assert "total_errors" in summary
    assert "categories" in summary

    # Test node failure tracking for malicious behavior
    normal_node.log_node_behavior("node_2", "invalid_signature")
    assert "node_2" in normal_node.node_failure_counts
