"""
Test suite for SubChain module

This module contains comprehensive unit tests for the SubChain class functionality,
including operation events, entity status updates, main chain connections,
proof generation, entity history tracking, and domain statistics.
"""
import time
from hierarchical.sub_chain import SubChain
from hierarchical.main_chain import MainChain


def test_sub_chain_creation():
    """Test basic SubChain creation"""
    sub_chain = SubChain(name="TestSubChain", domain_type="manufacturing")
    
    assert sub_chain.name == "TestSubChain"
    assert sub_chain.domain_type == "manufacturing"
    assert len(sub_chain.chain) == 1  # Genesis block
    assert sub_chain.completed_operations == 0


def test_operation_events():
    """Test starting and completing operations"""
    sub_chain = SubChain(name="OperationTestChain", domain_type="testing")
    
    # Start an operation
    result = sub_chain.start_operation("ENTITY-001", "production", {"batch": "BATCH-001"})
    
    assert result is True
    assert len(sub_chain.pending_events) == 1
    assert sub_chain.pending_events[0]["entity_id"] == "ENTITY-001"
    assert sub_chain.pending_events[0]["event"] == "operation_start"
    
    # Complete an operation
    result2 = sub_chain.complete_operation("ENTITY-001", "production", {"status": "completed"})
    
    assert result2 is True
    assert len(sub_chain.pending_events) == 2
    assert sub_chain.pending_events[1]["event"] == "operation_complete"
    assert sub_chain.completed_operations == 1


def test_entity_status_updates():
    """Test updating entity status"""
    sub_chain = SubChain(name="StatusTestChain", domain_type="testing")
    
    result = sub_chain.update_entity_status("ENTITY-001", "in_progress", {"step": 1})
    
    assert result is True
    assert len(sub_chain.pending_events) == 1
    assert sub_chain.pending_events[0]["event"] == "status_update"
    assert sub_chain.pending_events[0]["details"]["new_status"] == "in_progress"


def test_main_chain_connection():
    """Test connecting to MainChain"""
    main_chain = MainChain(name="ConnectionTestMainChain")
    sub_chain = SubChain(name="ConnectionTestSubChain", domain_type="testing")
    
    # Connect to main chain
    result = sub_chain.connect_to_main_chain(main_chain)
    
    assert result is True
    assert sub_chain.main_chain_connection == main_chain
    
    # Check that sub-chain is registered in main chain
    assert "ConnectionTestSubChain" in main_chain.registered_sub_chains


def test_proof_generation():
    """Test default proof metadata generation"""
    sub_chain = SubChain(name="ProofGenChain", domain_type="testing")
    
    # Add some operations to have data for proof
    sub_chain.start_operation("ENTITY-001", "test_op", {"data": "test"})
    sub_chain.finalize_sub_chain_block()
    
    # Generate default proof metadata
    metadata = sub_chain._generate_default_proof_metadata()
    
    assert "domain_type" in metadata
    assert "latest_block_index" in metadata
    assert "total_blocks" in metadata
    assert "recent_events" in metadata
    assert metadata["domain_type"] == "testing"


def test_entity_history():
    """Test retrieving entity history"""
    sub_chain = SubChain(name="HistoryTestChain", domain_type="testing")
    
    # Add events for an entity
    sub_chain.start_operation("ENTITY-001", "operation_1")
    sub_chain.complete_operation("ENTITY-001", "operation_1", {"result": "success"})
    sub_chain.update_entity_status("ENTITY-001", "completed")
    
    # Finalize events into blocks
    sub_chain.finalize_sub_chain_block()
    
    # Get entity history
    history = sub_chain.get_entity_history("ENTITY-001")
    
    assert len(history) == 3
    # Events should be sorted by timestamp
    assert history[0]["timestamp"] <= history[1]["timestamp"] <= history[2]["timestamp"]


def test_domain_statistics():
    """Test domain statistics"""
    sub_chain = SubChain(name="StatsTestChain", domain_type="testing")
    
    # Add some operations
    sub_chain.start_operation("ENTITY-001", "test_op")
    sub_chain.complete_operation("ENTITY-001", "test_op")
    sub_chain.start_operation("ENTITY-002", "test_op")
    
    # Finalize to blocks
    sub_chain.finalize_sub_chain_block()
    
    # Get statistics
    stats = sub_chain.get_domain_statistics()
    
    assert stats["name"] == "StatsTestChain"
    assert stats["domain_type"] == "testing"
    assert stats["unique_entities"] == 2
    assert stats["completed_operations"] == 1  # Only one completed
    assert stats["total_events"] >= 3  # At least our 3 events