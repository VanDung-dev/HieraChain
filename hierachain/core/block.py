"""
Block implementation for HieraChain Framework.

This module implements the Block class following the framework guidelines:
- Blocks contain multiple events, not one event per block
- Never equate a block with an entity
- Events are domain-specific operations with metadata
"""

import hashlib
import json
import time
from typing import List, Dict, Any, Optional, Union
import pyarrow as pa
import pyarrow.compute as pc

from hierachain.core import schemas


class Block:
    """
    Block class using Apache Arrow for high-performance event storage.
    
    Data Consistency:
    - Events are stored internally as a `pyarrow.Table`.
    - `self.events` property exposes this Table.
    - Hashing still uses strict JSON canonicalization for backward compatibility.
    """
    
    def __init__(self, index: int, events: Union[List[Dict[str, Any]], pa.Table], 
                 timestamp: Optional[float] = None, previous_hash: str = "", nonce: int = 0):
        """
        Initialize a new block.
        
        Args:
            index: Block index in the chain
            events: List of event dicts OR an existing Arrow Table
            timestamp: Block creation timestamp (defaults to current time)
            previous_hash: Hash of the previous block
            nonce: Nonce value
        """
        self.index = index
        self.timestamp = timestamp or time.time()
        self.previous_hash = previous_hash
        self.nonce = nonce
        
        # Initialize Arrow Table
        if isinstance(events, pa.Table):
            self._events = events
        else:
            self._events = self._convert_events_to_arrow(events)
            
        self.hash = self.calculate_hash()
    
    @property
    def events(self) -> pa.Table:
        """Access events as an Arrow Table."""
        return self._events

    @staticmethod
    def _convert_events_to_arrow(events_list: List[Dict[str, Any]]) -> pa.Table:
        """Helper to convert list of dicts to Arrow Table with schema."""
        if not events_list:
            # Create empty table with correct schema
            return pa.Table.from_pylist([], schema=schemas.get_event_schema())
        
        # Pre-process details to JSON strings if they are dicts
        processed_events = []
        for e in events_list:
            ev = e.copy()
            if isinstance(ev.get('details'), (dict, list)):
                ev['details'] = json.dumps(ev['details'])
            processed_events.append(ev)
            
        s = schemas.get_event_schema()
        return pa.Table.from_pylist(processed_events, schema=s)

    def calculate_hash(self) -> str:
        """
        Calculate the hash of the block.
        Converts Arrow data back to standard JSON structure for hashing.
        """
        events_list = self._table_to_list_of_dicts(self._events)
        
        block_data = {
            "index": self.index,
            "events": events_list,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }
        
        # Convert to JSON string with sorted keys for consistent hashing
        block_string = json.dumps(block_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def add_event(self, event: Dict[str, Any]) -> None:
        """
        Add an event to the block and recalculate hash.
        Performance warning: Creates new Arrow Table.
        """
        # Create a small table for the new event
        new_table = self._convert_events_to_arrow([event])
        if len(self._events) == 0:
            self._events = new_table
        else:
            self._events = pa.concat_tables([self._events, new_table])
        self.hash = self.calculate_hash()
    
    def get_events_by_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all events for a specific entity.
        Uses Arrow filtering.
        """
        filtered_table = self._events.filter(pc.equal(self._events['entity_id'], entity_id))
        return self._table_to_list_of_dicts(filtered_table)

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get all events of a specific type."""
        filtered_table = self._events.filter(pc.equal(self._events['event'], event_type))
        return self._table_to_list_of_dicts(filtered_table)
    
    def to_event_list(self) -> List[Dict[str, Any]]:
        """
        Convert internal Arrow events to a list of dictionaries.
        This provides a standard Python interface for consumers.
        """
        return self._table_to_list_of_dicts(self._events)

    @staticmethod
    def _table_to_list_of_dicts(table: pa.Table) -> List[Dict[str, Any]]:
        """Convert Arrow Table to list of dicts with parsed details."""
        events = []
        for row in table.to_pylist():
            if row.get('details'):
                try:
                    row['details'] = json.loads(row['details'])
                except (TypeError, json.JSONDecodeError):
                    pass
            events.append(row)
        return events

    def validate_structure(self) -> bool:
        """
        Validate the block structure.

        Returns:
            Checks if the internal event table conforms to the schema.
        """
        if not isinstance(self._events, pa.Table):
            return False
            
        # Verify schema matches expected Event Schema
        required = ['entity_id', 'event', 'timestamp']
        
        names = self._events.column_names
        for r in required:
            if r not in names:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert block to dictionary representation.
        
        Returns:
            Dictionary representation of the block
        """
        return {
            "index": self.index,
            "events": self._table_to_list_of_dicts(self._events),
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        """
        Create a Block instance from dictionary data.
        
        Args:
            data: Dictionary containing block data
            
        Returns:
            Block instance
        """
        block = cls(
            index=data["index"],
            events=data["events"],
            timestamp=data["timestamp"],
            previous_hash=data["previous_hash"],
            nonce=data.get("nonce", 0)
        )
        return block # Hash is recalculated in init

    def __str__(self) -> str:
        """String representation of the block."""
        return f"Block(index={self.index}, events_count={len(self._events)}, hash={self.hash[:10]}...)"
    
    def __repr__(self) -> str:
        """Detailed string representation of the block."""
        return (f"Block(index={self.index}, events={len(self._events)}, "
                f"timestamp={self.timestamp}, hash={self.hash})")