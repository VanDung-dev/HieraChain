"""
Tests for data consistency in the Block class.

This test suite is designed to ensure that the Block class handles data
correctly and consistently.
"""

import time
import json
import sys
import os
import pyarrow as pa

from hierachain.core import Block

# Ensure project root is in path
sys.path.append(os.getcwd())


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
    
    assert isinstance(block._events, pa.Table)
    
    events_list = block.to_event_list()
    assert isinstance(events_list, list)
    assert len(events_list) == 2
    assert isinstance(events_list[0], dict)
    assert events_list[0]['entity_id'] == "test_entity_1"

def test_json_serialization():
    """Test that to_event_list() output is JSON serializable (fixes API crash)."""
    block = create_test_block()
    
    events_data = block.to_event_list()
    
    try:
        json_str = json.dumps(events_data)
        assert len(json_str) > 0
    except TypeError as e:
        raise AssertionError(f"Event list is not JSON serializable: {e}")
