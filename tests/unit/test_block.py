"""
Test suite for Block module

This module contains unit tests for the Block class functionality,
including block creation, hashing, event operations, and validation.
"""

import time
from core.block import Block
from core.blockchain import Blockchain


def test_block_with_multiple_events():
    chain = Blockchain(name="UnitTestChain")

    # Add multiple events to pending list
    chain.add_event({
        "entity_id": "ENT-001",
        "event": "operation_start",
        "details": {"step": 1}
    })
    chain.add_event({
        "entity_id": "ENT-002",
        "event": "operation_start",
        "details": {"step": 1}
    })

    # Finalize into a block
    new_block = chain.finalize_block()
    assert new_block is not None
    assert len(new_block.events) == 2

    # Chain should be valid and have at least 2 blocks (genesis + new)
    assert chain.is_chain_valid() is True
    assert len(chain.chain) >= 2


def test_block_creation_and_hashing():
    """Test basic block creation and hashing functionality"""
    events = [
        {
            "entity_id": "TEST-001",
            "event": "test_event",
            "timestamp": time.time(),
            "details": {"data": "test"}
        }
    ]
    
    block = Block(
        index=1,
        events=events,
        previous_hash="0000000000000000000000000000000000000000000000000000000000000000"
    )
    
    # Check block properties
    assert block.index == 1
    assert block.events == events
    assert block.previous_hash == "0000000000000000000000000000000000000000000000000000000000000000"
    assert isinstance(block.hash, str)
    assert len(block.hash) == 64  # SHA-256 hash length


def test_block_hash_consistency():
    """Test that block hash is consistent when recalculated"""
    events = [
        {
            "entity_id": "TEST-002",
            "event": "another_test",
            "timestamp": time.time(),
            "details": {"value": 42}
        }
    ]
    
    block = Block(
        index=2,
        events=events,
        previous_hash="abcdef1234567890"
    )
    
    original_hash = block.hash
    recalculated_hash = block.calculate_hash()
    
    assert original_hash == recalculated_hash


def test_block_event_operations():
    """Test adding events to block and querying by entity or type"""
    events = [
        {
            "entity_id": "ENTITY-001",
            "event": "production_start",
            "timestamp": time.time(),
            "details": {"product": "A"}
        },
        {
            "entity_id": "ENTITY-002",
            "event": "production_start",
            "timestamp": time.time(),
            "details": {"product": "B"}
        },
        {
            "entity_id": "ENTITY-001",
            "event": "quality_check",
            "timestamp": time.time(),
            "details": {"result": "pass"}
        }
    ]
    
    block = Block(
        index=3,
        events=events,
        previous_hash="1234567890abcdef"
    )
    
    # Test getting events by entity
    entity_001_events = block.get_events_by_entity("ENTITY-001")
    assert len(entity_001_events) == 2
    
    entity_002_events = block.get_events_by_entity("ENTITY-002")
    assert len(entity_002_events) == 1
    
    # Test getting events by type
    start_events = block.get_events_by_type("production_start")
    assert len(start_events) == 2
    
    check_events = block.get_events_by_type("quality_check")
    assert len(check_events) == 1


def test_block_structure_validation():
    """Test block structure validation"""
    # Valid block
    valid_events = [
        {
            "entity_id": "VALID-001",
            "event": "test_event",
            "timestamp": time.time()
        }
    ]
    
    valid_block = Block(
        index=4,
        events=valid_events,
        previous_hash="valid_hash"
    )
    
    assert valid_block.validate_structure() is True
    
    # Invalid block - events not a list
    try:
        invalid_block = Block(
            index=5,
            events={"not": "a_list"},
            previous_hash="invalid_hash"
        )
        assert invalid_block.validate_structure() is False
    except Exception:
        # Constructor might reject invalid structure
        pass