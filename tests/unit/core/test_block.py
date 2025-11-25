"""
Test suite for Block module

This module contains unit tests for the Block class functionality,
including block creation, hashing, event operations, and validation.
"""

import time
import random
import string
from hypothesis import given, strategies as st

from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain


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

    # Invalid block - events with invalid structure
    try:
        invalid_block = Block(
            index=5,
            events=[{"invalid": "structure", "missing_required_fields": True}],
            previous_hash="invalid_hash"
        )
        assert invalid_block.validate_structure() is False
    except (ValueError, TypeError):
        # Constructor might reject invalid structure
        pass


def test_block_with_zero_events():
    """Test block creation with zero events"""
    block = Block(
        index=1,
        events=[],  # Empty events list
        previous_hash="0000000000000000000000000000000000000000000000000000000000000000"
    )

    # Check block properties
    assert block.index == 1
    assert len(block.events) == 0
    assert block.previous_hash == "0000000000000000000000000000000000000000000000000000000000000000"
    assert isinstance(block.hash, str)
    assert len(block.hash) == 64  # SHA-256 hash length

    # Block with zero events should be valid
    assert block.validate_structure() is True



def test_block_performance_with_large_number_of_events(benchmark):
    """Test block performance with large number of events"""
    def execute():
        # Create a large number of events
        large_event_set = []
        for i in range(1000):  # 1000 events
            large_event_set.append({
                "entity_id": f"LARGE-EVENT-{i}",
                "event": "bulk_operation",
                "timestamp": time.time(),
                "details": {"data": f"value_{i}"}
            })

        # Measure time to create block
        start_time = time.time()
        block = Block(
            index=1,
            events=large_event_set,
            previous_hash="0000000000000000000000000000000000000000000000000000000000000000"
            )
        end_time = time.time()

        # Check block was created successfully
        assert block.index == 1
        assert len(block.events) == 1000
        assert isinstance(block.hash, str)
        assert len(block.hash) == 64  # SHA-256 hash length

        # Performance assertion - should complete within reasonable time (less than 2 seconds)
        assert (end_time - start_time) < 2.0

        return block

    benchmark(execute)


def test_block_invalid_hash():
    """Test block with invalid hash scenarios"""
    events = [
        {
            "entity_id": "HASH-TEST-001",
            "event": "hash_test_event",
            "timestamp": time.time(),
            "details": {"data": "test"}
        }
    ]

    block = Block(
        index=1,
        events=events,
        previous_hash="0000000000000000000000000000000000000000000000000000000000000000"
    )

    # Valid hash initially
    assert isinstance(block.hash, str)
    assert len(block.hash) == 64

    # Test with manipulated hash
    original_hash = block.hash
    block.hash = "invalid_hash_value"  # Manipulate the hash

    # Recalculate should give us the correct hash again
    recalculated_hash = block.calculate_hash()
    assert recalculated_hash == original_hash
    assert recalculated_hash != block.hash  # manipulated hash should be different


# Property-based testing with Hypothesis
@given(st.integers(min_value=0, max_value=1000),
       st.lists(st.dictionaries(st.text(), st.text(), min_size=1), min_size=0, max_size=100),
       st.text(min_size=64, max_size=64))
def test_block_hash_property(index, events, previous_hash):
    """Property-based test for block hash generation consistency"""
    # Ensure previous_hash is 64 characters (SHA-256)
    previous_hash = previous_hash[:64]

    block = Block(index=index, events=events, previous_hash=previous_hash)

    # Hash should always be 64 characters (SHA-256)
    assert len(block.hash) == 64
    assert isinstance(block.hash, str)

    # Hash should be consistent
    assert block.hash == block.calculate_hash()


@given(st.lists(st.dictionaries(st.text(min_size=1), st.text(min_size=1)), min_size=1, max_size=50))
def test_block_event_operations_property(events):
    """Property-based test for block event operations"""
    block = Block(index=1, events=events, previous_hash="0" * 64)

    # All events should be retrievable by their event type
    for event in events:
        if "event" in event:
            found_events = block.get_events_by_type(event["event"])
            assert len(found_events) >= 1
            assert event in found_events


# Fuzz testing
def test_block_with_fuzzed_data():
    """Fuzz testing with randomized inputs"""
    # Generate random events with various data types
    events = []
    for i in range(20):
        # Random entity_id
        entity_id = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(5, 20)))

        # Random event type
        event_type = ''.join(random.choices(string.ascii_letters, k=random.randint(3, 15)))

        # Random details with various data
        details = {
            "random_str": ''.join(random.choices(string.printable, k=random.randint(1, 100))),
            "random_int": random.randint(-1000000, 1000000),
            "random_float": random.uniform(-1000.0, 1000.0),
            "random_bool": random.choice([True, False])
        }

        events.append({
            "entity_id": entity_id,
            "event": event_type,
            "timestamp": time.time() + random.uniform(-1000000, 1000000),
            "details": details
        })

    # Create block with fuzzed data
    block = Block(
        index=random.randint(0, 10000),
        events=events,
        previous_hash=''.join(random.choices('0123456789abcdef', k=64))
    )

    # Block should still be valid
    assert isinstance(block.hash, str)
    assert len(block.hash) == 64
    assert block.validate_structure() is True

    # Events should be retrievable
    for event in events:
        if "entity_id" in event:
            entity_events = block.get_events_by_entity(event["entity_id"])
            assert len(entity_events) >= 1
