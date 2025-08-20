"""
Test suite for BFT Consensus Mechanism

This module contains unit tests for the BFTConsensus class,
including message handling, consensus phases, and node communication.
"""
from hierarchical.consensus.bft_consensus import BFTConsensus, create_bft_network, ConsensusError
import time


def test_bft_network_creation():
    """Test creation of BFT network"""
    # Valid configuration
    node_configs = [
        {"node_id": "node_1"},
        {"node_id": "node_2"},
        {"node_id": "node_3"},
        {"node_id": "node_4"}
    ]
    
    # Should work with enough nodes for f=1
    network = create_bft_network(node_configs, fault_tolerance=1)
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
    node_ids = ["node_1", "node_2", "node_3", "node_4"]
    bft = BFTConsensus("node_1", node_ids, f=1)
    
    assert bft.node_id == "node_1"
    assert bft.n == 4  # Total nodes
    assert bft.f == 1  # Fault tolerance
    assert bft.view == 0
    assert bft.sequence_number == 0
    assert len(bft.all_nodes) == 4
    assert bft.state.value == "idle"


def test_bft_primary_determination():
    """Test primary node determination"""
    node_ids = ["node_1", "node_2", "node_3", "node_4"]
    bft = BFTConsensus("node_1", node_ids, f=1)
    
    # In view 0, primary should be node_1 (first in sorted list)
    assert bft._primary() == "node_1"
    assert bft._is_primary() is True
    
    # Test with different node
    bft2 = BFTConsensus("node_2", node_ids, f=1)
    assert bft2._primary() == "node_1"  # Still node_1 in view 0
    assert bft2._is_primary() is False  # node_2 is not primary