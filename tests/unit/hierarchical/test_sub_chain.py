"""
Test suite for SubChain module

This module contains comprehensive unit tests for the SubChain class functionality,
including operation events, entity status updates, main chain connections,
proof generation, entity history tracking, and domain statistics.
"""

from unittest.mock import Mock, patch

from hierarchical_blockchain.hierarchical.sub_chain import SubChain
from hierarchical_blockchain.hierarchical.main_chain import MainChain


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


# New tests for invalid inputs
def test_sub_chain_creation_with_invalid_inputs():
    """Test SubChain creation with invalid inputs"""
    # Test with empty name
    sub_chain = SubChain(name="", domain_type="manufacturing")
    assert sub_chain.name == ""
    assert sub_chain.domain_type == "manufacturing"
    
    # Test with empty domain type
    sub_chain = SubChain(name="TestChain", domain_type="")
    assert sub_chain.name == "TestChain"
    assert sub_chain.domain_type == ""


def test_operation_events_with_invalid_inputs():
    """Test operation events with invalid inputs"""
    sub_chain = SubChain(name="InvalidOpTestChain", domain_type="testing")
    
    # Test with empty entity_id
    result = sub_chain.start_operation("", "production", {"batch": "BATCH-001"})
    assert result is True
    assert sub_chain.pending_events[0]["entity_id"] == ""
    
    # Test with empty operation_type
    result = sub_chain.start_operation("ENTITY-002", "", {"batch":"BATCH-002"})
    assert result is True
    assert sub_chain.pending_events[1]["details"]["operation_type"] == ""
    
    # Test with None details
    result = sub_chain.start_operation("ENTITY-003", "production", None)
    assert result is True
    assert sub_chain.pending_events[2]["details"]["operation_details"] == {}


def test_entity_status_updates_with_invalid_inputs():
    """Test entity status updates with invalid inputs"""
    sub_chain = SubChain(name="InvalidStatusTestChain", domain_type="testing")
    
    # Test with empty entity_id
    result = sub_chain.update_entity_status("","in_progress", {"step": 1})
    assert result is True
    assert sub_chain.pending_events[0]["entity_id"] == ""
    
    # Test with empty status
    result = sub_chain.update_entity_status("ENTITY-001", "", {"step": 2})
    assert result is True
    assert sub_chain.pending_events[1]["details"]["new_status"] == ""
    
    # Test with None details
    result = sub_chain.update_entity_status("ENTITY-002", "completed", None)
    assert result is True
    assert sub_chain.pending_events[2]["details"]["status_details"] == {}


def test_main_chain_connection_with_invalid_inputs():
    """Test main chain connection with invalid inputs"""
    sub_chain = SubChain(name="InvalidConnectionTestSubChain", domain_type="testing")
    
    # Test with None main_chain
    result = sub_chain.connect_to_main_chain(None)
    assert result is False
    assert sub_chain.main_chain_connection is None
    
    # Test with invalid main_chain object (missing required methods)
    invalid_main_chain = {}
    result = sub_chain.connect_to_main_chain(invalid_main_chain)
    assert result is False


def test_proof_submission_with_invalid_inputs():
    """Test proof submissionwith invalidinputs"""
    sub_chain = SubChain(name="InvalidProofTestChain", domain_type="testing")
    
    # Test with None main_chain
    result = sub_chain.submit_proof_to_main(None)
    assert result is False
    
    # Test with invalid main_chain object
    invalid_main_chain = {}
    result = sub_chain.submit_proof_to_main(invalid_main_chain)
    assert result is False


# Performance benchmark test
def test_sub_chain_performance(benchmark):
    """Benchmark SubChain performance with multiple operations"""
    def run_performance_test():
        sub_chain = SubChain(name="PerformanceTestChain", domain_type="testing")
        
        # Add many operations
        for i in range(1000):
            sub_chain.start_operation(f"ENTITY-{i:04d}", f"operation_{i}", {"data": f"value_{i}"})
            
        # Complete half of them
        for i in range(0, 1000, 2):
            sub_chain.complete_operation(f"ENTITY-{i:04d}", f"operation_{i}", {"status": "completed"})
        
        # Finalize blocks
        for _ in range(10):
            sub_chain.finalize_sub_chain_block()
        
        return sub_chain

    chain = benchmark(run_performance_test)
    
    # Basic assertions to ensure it worked
    assert chain.completed_operations == 500
    assert len(chain.chain) > 1


# Mock dependency tests
def test_sub_chain_with_mock_main_chain():
    """Test SubChain with mocked MainChain"""
    sub_chain = SubChain(name="MockTestChain", domain_type="testing")
    
    # Create a mock main chain
    mock_main_chain = Mock()
    mock_main_chain.register_sub_chain.return_value = True
    mock_main_chain.add_proof.return_value = True
    mock_main_chain.name = "MockMainChain"  # Add name attribute to avoid serialization issues
    
    # Connect to mock main chain
    result = sub_chain.connect_to_main_chain(mock_main_chain)
    assert result is True
    assert sub_chain.main_chain_connection == mock_main_chain
    
    # Verify mock was called correctly
    mock_main_chain.register_sub_chain.assert_called_once()
    
    # Test proof submission with mock
    sub_chain.start_operation("ENTITY-001", "test_operation")
    sub_chain.finalize_sub_chain_block()
    
    result = sub_chain.submit_proof_to_main(mock_main_chain)
    assert result is True
    mock_main_chain.add_proof.assert_called_once()


@patch('hierarchical_blockchain.hierarchical.sub_chain.time')
def test_auto_proof_submission_with_mock_time(mock_time):
    """Test automatic proof submission with mocked time"""
    # Setup mock time
    mock_time.time.return_value = 0
    
    sub_chain = SubChain(name="AutoSubmitTestChain", domain_type="testing")
    sub_chain.proof_submission_interval = 30.0  # 30 seconds
    
    # Create a mock main chain
    mock_main_chain = Mock()
    mock_main_chain.register_sub_chain.return_value = True
    mock_main_chain.add_proof.return_value = True
    mock_main_chain.name = "MockMainChain"  # Add name attribute to avoid serialization issues
    
    # Connect to mock main chain
    sub_chain.connect_to_main_chain(mock_main_chain)
    
    # Add an operation
    sub_chain.start_operation("ENTITY-001", "test_operation")
    
    # Test should_submit_proof with time before interval
    mock_time.time.return_value = 15  # 15 seconds passed
    assert sub_chain.should_submit_proof() is False
    
    # Add another operation to ensure pending_events is not empty after finalize_sub_chain_block
    sub_chain.start_operation("ENTITY-002", "test_operation2")
    
    # Finalize the first block (this will clear pending_events but then we add another operation)
    sub_chain.finalize_sub_chain_block()
    
    # Add another operation to have pending events
    sub_chain.start_operation("ENTITY-003", "test_operation3")
    
    # Test should_submit_proof with time after interval
    mock_time.time.return_value = 60  # 60 seconds passed
    assert sub_chain.should_submit_proof() is True
    
    # Test auto submission
    result = sub_chain.auto_submit_proof_if_needed()
    assert result is True
    mock_main_chain.add_proof.assert_called_once()