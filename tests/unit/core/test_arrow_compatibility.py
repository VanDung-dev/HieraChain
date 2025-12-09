"""
Test cases for Arrow compatibility of Block class

This module contains test cases for the Block class to ensure its compatibility with Apache Arrow.
It tests the conversion of events to and from Arrow tables, as well as the addition of events to a block.
"""

import time
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

import pyarrow as pa
from hierachain.core.block import Block

# Test case for Arrow compatibility of Block class
# This test verifies that Block can properly convert events to and from Arrow tables
def test_arrow_conversion():
    """
    Test Arrow conversion functionality
    Verifies that events are properly converted to Arrow tables and maintains data integrity
    """
    events = [
        {'entity_id': 'e1', 'event': 't1', 'timestamp': 1.0, 'details': {'key': 'value1'}},
        {'entity_id': 'e2', 'event': 't2', 'timestamp': 2.0, 'details': {'nums': [1, 2, 3]}},
        {'entity_id': 'e3', 'event': 't3', 'timestamp': 3.0, 'details': None},
    ]
    
    # Initialize block with list of dicts
    block = Block(1, events, timestamp=100.0)
    
    # Verify internal storage is Arrow Table
    assert isinstance(block.events, pa.Table)
    assert len(block.events) == 3
    
    # Verify schema
    schema = block.events.schema
    assert schema.field('details').type == pa.map_(pa.string(), pa.string())
    
    # Verify data integrity via to_dict (which converts back)
    block_dict = block.to_dict()
    events_out = block_dict['events']
    
    assert len(events_out) == 3
    assert events_out[0]['details'] == {'key': 'value1'}
    assert events_out[1]['details'] == {'nums': str([1, 2, 3])}
    # Details None might come back as None or empty dict depending on impl, let's check
    # In current impl, if details is None, we store None/null in Arrow.
    # JSON string for None is 'null' or actual null in Arrow.
    # _convert_events_to_arrow handles this.
    assert events_out[2].get('details') == {}

# Test adding events to a block
def test_add_event():
    """
    Test adding events to a block
    Verifies that events can be added to an existing block and are properly stored
    """
    block = Block(1, [], timestamp=100.0)
    assert len(block.events) == 0
    
    new_event = {'entity_id': 'e1', 'event': 't1', 'timestamp': 1.0, 'details': {'a': 1}}
    block.add_event(new_event)
    
    assert len(block.events) == 1
    assert isinstance(block.events, pa.Table)
    
    out = block.to_dict()['events'][0]
    assert out['details'] == {'a': '1'}

# Test filtering events by entity or type
def test_filtering():
    """
    Test event filtering functionality
    Verifies that events can be filtered by entity ID or event type
    """
    events = [
        {'entity_id': 'A', 'event': 'type1', 'timestamp': 1.0},
        {'entity_id': 'B', 'event': 'type1', 'timestamp': 2.0},
        {'entity_id': 'A', 'event': 'type2', 'timestamp': 3.0},
    ]
    block = Block(1, events)
    
    # Filter by entity
    a_events = block.get_events_by_entity('A')
    assert len(a_events) == 2
    assert all(e['entity_id'] == 'A' for e in a_events)
    
    # Filter by type
    t1_events = block.get_events_by_type('type1')
    assert len(t1_events) == 2

# Performance benchmark test
def test_performance_bench():
    """
    Performance benchmark test
    Verifies that block creation with large number of events is reasonably fast
    """
    # Quick perf check
    start = time.time()
    events = [{'entity_id': f'e{i}', 'event': 't', 'timestamp': float(i), 'details': {'i': i}} for i in range(1000)]
    block = Block(1, events)
    duration = time.time() - start
    print(f"Time to create block with 1000 events: {duration:.4f}s")
    assert duration < 1.0
