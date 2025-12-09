"""
Test suite for Blockchain core module

This module contains comprehensive tests for the Blockchain core functionality,
including block creation, event management, chain validation, and entity-based
event retrieval. The tests ensure the HieraChain maintains data
integrity and follows the project's architectural principles.
"""

import time
import pytest
import random
import string

from hierachain.core.blockchain import Blockchain
from hierachain.core.block import Block


def test_blockchain_creation():
    """Test basic blockchain creation and genesis block"""
    chain = Blockchain(name="TestChain")

    # Should have genesis block
    assert len(chain.chain) == 1
    assert chain.name == "TestChain"
    assert chain.chain[0].index == 0


def test_event_adding():
    """Test adding events to pending list"""
    chain = Blockchain(name="EventTestChain")

    event = {
        "entity_id": "EVENT-001",
        "event": "test_operation",
        "timestamp": time.time(),
        "details": {"value": "test"}
    }

    chain.add_event(event)

    assert len(chain.pending_events) == 1
    assert chain.pending_events[0]["entity_id"] == "EVENT-001"
    assert chain.pending_events[0]["event"] == "test_operation"


def test_block_creation():
    """Test creating blocks from pending events"""
    chain = Blockchain(name="BlockCreationChain")

    # Add some events
    events = [
        {
            "entity_id": "BLOCK-001",
            "event": "operation_1",
            "timestamp": time.time()
        },
        {
            "entity_id": "BLOCK-002",
            "event": "operation_2",
            "timestamp": time.time()
        }
    ]

    for event in events:
        chain.add_event(event)

    # Create block with pending events
    block = chain.create_block()

    assert isinstance(block, Block)
    assert block.index == 1  # Genesis block is 0
    assert len(block.events) == 2
    assert block.previous_hash == chain.get_latest_block().hash


def test_block_adding_and_validation():
    """Test adding blocks to chain and chain validation"""
    chain = Blockchain(name="BlockAddTestChain")

    # Add events and create block
    chain.add_event({
        "entity_id": "VALIDATION-001",
        "event": "test_event",
        "timestamp": time.time()
    })

    block = chain.create_block()
    result = chain.add_block(block)

    assert result is True
    assert len(chain.chain) == 2  # Genesis + new block
    assert chain.is_chain_valid() is True


def test_entity_event_retrieval():
    """Test retrieving events by entity ID"""
    chain = Blockchain(name="EntityRetrievalChain")

    # Add events for different entities
    events = [
        {
            "entity_id": "ENTITY-A",
            "event": "start_process",
            "timestamp": time.time()
        },
        {
            "entity_id": "ENTITY-B",
            "event": "start_process",
            "timestamp": time.time()
        },
        {
            "entity_id": "ENTITY-A",
            "event": "complete_process",
            "timestamp": time.time()
        }
    ]

    for event in events:
        chain.add_event(event)

    # Finalize block
    chain.finalize_block()

    # Retrieve events by entity
    entity_a_events = chain.get_events_by_entity("ENTITY-A")
    entity_b_events = chain.get_events_by_entity("ENTITY-B")

    assert len(entity_a_events) == 2
    assert len(entity_b_events) == 1


def test_chain_statistics():
    """Test chain statistics functionality"""
    chain = Blockchain(name="StatsTestChain")

    # Add some events
    for i in range(3):
        chain.add_event({
            "entity_id": f"STATS-{i}",
            "event": "stat_event",
            "timestamp": time.time()
        })

    # Finalize block
    chain.finalize_block()

    stats = chain.get_chain_stats()

    assert stats["name"] == "StatsTestChain"
    assert stats["total_blocks"] == 2  # Genesis + 1 new
    assert stats["total_events"] == 4  # 1 from genesis block + 3 added events
    assert stats["pending_events"] == 0
    assert stats["chain_valid"] is True


def test_blockchain_fork_and_reorganization():
    """Test blockchain fork and chain reorganization"""
    # Create main chain
    main_chain = Blockchain(name="MainChain")

    # Add some events to main chain
    for i in range(3):
        main_chain.add_event({
            "entity_id":f"MAIN-{i}",
            "event": "main_event",
            "timestamp": time.time()
        })
        main_chain.finalize_block()

    # Create forked chain from genesis
    fork_chain = Blockchain(name="ForkChain")
    # Copy genesis block
    fork_chain.chain = [main_chain.chain[0]]

    # Add events to fork chain
    for i in range(5):  # More blocks in fork
        fork_chain.add_event({
            "entity_id": f"FORK-{i}",
            "event": "fork_event",
            "timestamp": time.time()
        })
        fork_chain.finalize_block()

    # Verify fork chain is longer
    assert len(fork_chain.chain) > len(main_chain.chain)

    # Test chain validity for both
    assert main_chain.is_chain_valid() is True
    assert fork_chain.is_chain_valid() is True


def test_blockchain_with_malicious_blocks():
    """Test blockchain behavior with malicious blocks"""
    chain = Blockchain(name="MaliciousTestChain")

    # Add some legitimate events and blocks
    chain.add_event({
        "entity_id": "LEGIT-001",
        "event": "legit_event",
        "timestamp": time.time()
    })
    chain.finalize_block()

    # Try to add a block with tampered data (malicious)
    malicious_block = Block(
        index=2,
        events=[{
            "entity_id": "MALICIOUS-001",
            "event": "malicious_event",
            "timestamp": time.time()
        }],
        previous_hash="tampered_fake_hash"  # Intentionally wrong hash
    )

    # Attempt to add malicious block
    result = chain.add_block(malicious_block)

    # Should either reject the block or mark chain as invalid
    # Depending on implementation, this might return False or make chain invalid
    if not result is True:
        assert result is False  # Block rejected
    else:
        # If block was added, chain should be invalid
        assert chain.is_chain_valid() is False


# Performance/load testing
def test_blockchain_performance_with_large_number_of_events(benchmark):
    """Test blockchain performance with large number of events"""

    def create_and_process_events():
        chain = Blockchain(name="PerformanceTestChain")

        # Add a large number of events
        num_events = 5000

        for i in range(num_events):
            chain.add_event({
                "entity_id": f"PERF-{i}",
                "event": f"perf_event_{i % 100}",
                "timestamp": time.time(),
                "details": {
                    "data": f"sample_data_{i}",
                    "value": random.random(),
                    "iteration": i
                }
            })

        # Finalize multiple blocks
        blocks_created = 0
        while chain.pending_events:
            block = chain.finalize_block()
            if block:
                blocks_created += 1

        return chain, blocks_created

    # Benchmark the whole process
    chain, blocks_created = benchmark(create_and_process_events)

    # Verify chain integrity
    assert chain.is_chain_valid() is True
    assert len(chain.chain) == blocks_created + 1  # +1 for genesis block
    assert len(chain.pending_events) == 0


# Property-based testing
@pytest.mark.parametrize("num_events", [0, 1, 10, 100])
def test_blockchain_event_processing_property(num_events):
    """Property-based test for blockchain event processing"""
    chain = Blockchain(name=f"PropertyTestChain-{num_events}")

    # Add specified number of events
    for i in range(num_events):
        chain.add_event({
            "entity_id": f"PROP-{i}",
            "event": "property_test_event",
            "timestamp": time.time()
        })

    # Count events before finalizing
    pending_events_before = len(chain.pending_events)
    assert pending_events_before == num_events

    # Finalize if there are events
    if num_events > 0:
        block = chain.finalize_block()
        assert block is not None
        assert len(block.events) == num_events
    else:
        block = chain.finalize_block()
        assert block is None

    # No pending events after finalizing
    assert len(chain.pending_events) == 0

    # Chain should be valid
    assert chain.is_chain_valid() is True


# Fuzz testing
def test_blockchain_with_fuzzed_events():
    """Fuzz testing with randomized event data"""
    chain = Blockchain(name="FuzzTestChain")

    # Generate fuzzed events
    for i in range(100):
        # Random entity_id
        entity_id = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(1, 100)))

        # Random event type
        event_type = ''.join(random.choices(string.printable, k=random.randint(1, 50)))

        # Random details
        details = {}
        for j in range(random.randint(0, 20)):
            key = ''.join(random.choices(string.ascii_letters, k=random.randint(1, 20)))
            value_type = random.choice(["string", "int", "float", "bool", "list", "dict"])

            if value_type == "string":
                value = ''.join(random.choices(string.printable, k=random.randint(0, 100)))
            elif value_type == "int":
                value = random.randint(-1000000, 1000000)
            elif value_type == "float":
                value = random.uniform(-1000000.0, 1000000.0)
            elif value_type == "bool":
                value = random.choice([True, False])
            elif value_type == "list":
                value = [random.random() for _ in range(random.randint(0, 10))]
            else:  # dict
                value = {f"key_{k}": random.random() for k in range(random.randint(0, 5))}

            details[key] = value

        # Create event with fuzzed data
        event = {
            "entity_id": entity_id,
            "event": event_type,
            "timestamp": time.time() + random.uniform(-1000000, 1000000)  # Random timestamp
        }

        if details:
            event["details"] = details

        # Add event to chain
        try:
            chain.add_event(event)
        except (TypeError, ValueError):
            # Some malformed events might be rejected, which is fine
            pass

    # Try to finalize a block with valid events
    if chain.pending_events:
        try:
            block = chain.finalize_block()
            if block:
                # If we successfully created a block, chain should be valid
                assert chain.is_chain_valid() is True
        except (TypeError, ValueError):
            # Block creation might fail with invalid events, which is fine
            pass


# Integration testing between modules
def test_blockchain_block_cache_integration():
    """Integration test between blockchain and block modules"""
    chain = Blockchain(name="IntegrationTestChain")

    # Add events and create blocks
    for block_index in range(5):
        for event_index in range(10):
            chain.add_event({
                "entity_id": f"INT-{block_index}-{event_index}",
                "event": f"int_event_{event_index}",
                "timestamp": time.time(),
                "details": {
                    "block": block_index,
                    "event": event_index
                }
            })

        # Finalize block
        block = chain.finalize_block()
        assert block is not None
        assert isinstance(block, Block)
        assert block.index == block_index + 1  # +1 for genesis

    # Verify chain integrity
    assert chain.is_chain_valid() is True

    # Test event retrieval by entity
    events = chain.get_events_by_entity("INT-2-5")
    assert len(events) == 1
    assert events[0]["details"]["block"] == str(2)
    assert events[0]["details"]["event"] == str(5)

    # Test event retrieval by type
    type_events = chain.get_events_by_type("int_event_3")
    assert len(type_events) == 5  # One per block

    # Test chain statistics
    stats = chain.get_chain_stats()
    assert stats["total_blocks"] == 6  # Genesis + 5 created
    assert stats["total_events"] == 51  # 1 from genesis + 50 added
    assert stats["chain_valid"] is True
