"""
Tests for data consistency in the Block and WorldState classes.

This test suite is designed to ensure that the Block and WorldState classes
handle data correctly and consistently. It checks for data types, conversions,
and the integrity of the data structures used internally.
"""

import time
import json
import sys
import os
import pyarrow as pa

# Ensure project root is in path
sys.path.append(os.getcwd())

from hierachain.core.block import Block
from hierachain.storage.world_state import WorldState

def create_test_block() -> Block:
    events = [
        {
            "entity_id": "test_entity_1",
            "event": "creation",
            "timestamp": time.time(),
            "details": {"foo": "bar"}
        },
        {
            "entity_id": "test_entity_1",
            "event": "update",
            "timestamp": time.time(),
            "details": {"foo": "baz"},
            "updates": {"status": "updated"}
        }
    ]
    return Block(index=1, events=events, previous_hash="0"*64)

def test_block_arrow_interop():
    """Test that Block correctly converts Arrow data to python dicts."""
    block = create_test_block()
    
    # internal storage should be Arrow
    assert isinstance(block._events, pa.Table)
    
    # Public method should return List[Dict]
    events_list = block.to_event_list()
    assert isinstance(events_list, list)
    assert len(events_list) == 2
    assert isinstance(events_list[0], dict)
    assert events_list[0]['entity_id'] == "test_entity_1"

def test_world_state_update():
    """Test that WorldState can consume Arrow-backed blocks."""
    block = create_test_block()
    ws = WorldState("test_chain")
    
    # This should not crash and should update state
    ws.update_from_block(block)
    
    # Verify state was actually updated
    state = ws.get_entity_state("test_entity_1")
    assert state is not None
    assert state.get("status") == "updated"
    # Note: update event handling depends on WorldState logic, checking simple existence first

def test_json_serialization():
    """Test that to_event_list() output is JSON serializable (fixes API crash)."""
    block = create_test_block()
    
    # This simulates what the API should do: call to_event_list()
    events_data = block.to_event_list()
    
    try:
        json_str = json.dumps(events_data)
        assert len(json_str) > 0
    except TypeError as e:
        raise AssertionError(f"Event list is not JSON serializable: {e}")
