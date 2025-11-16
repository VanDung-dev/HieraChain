"""
Test suite for Blockchain core module

This module contains comprehensive tests for the Blockchain core functionality,
including block creation, event management, chain validation, and entity-based
event retrieval. The tests ensure the hierarchical blockchain maintains data
integrity and follows the project's architectural principles.
"""

import time

from hierarchical_blockchain.core.blockchain import Blockchain
from hierarchical_blockchain.core.block import Block


def test_blockchain_creation():
    """Test basic blockchain creation and genesis block"""
    chain = Blockchain(name="TestChain")
    
    # Should have genesis block
    assert len(chain.chain) == 1
    assert chain.name == "TestChain"
    assert chain.chain[0].index == 0
    assert len(chain.pending_events) == 0


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