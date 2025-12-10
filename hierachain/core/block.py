"""
Block implementation for HieraChain Framework.

This module implements the Block class following the framework guidelines:
- Blocks contain multiple events, not one event per block
- Never equate a block with an entity
- Events are domain-specific operations with metadata
"""

import time
from typing import List, Dict, Any, Optional, Union
import pyarrow as pa
import pyarrow.compute as pc

from hierachain.core import schemas
from hierachain.core.utils import MerkleTree, generate_hash


class Block:
    """
    Block class using Apache Arrow for high-performance event storage.
    
    Data Consistency:
    - Events are stored internally as a `pyarrow.Table`.
    - `self.events` property exposes this Table.
    - Hashing still uses strict JSON canonicalization for backward compatibility.
    """
    
    def __init__(self, index: int, events: Union[List[Dict[str, Any]], pa.Table], 
                 timestamp: Optional[float] = None, previous_hash: str = "", 
                 nonce: int = 0, merkle_root: Optional[str] = None):
        """
        Initialize a new block.
        
        Args:
            index: Block index in the chain
            events: List of event dicts OR an existing Arrow Table
            timestamp: Block creation timestamp (defaults to current time)
            previous_hash: Hash of the previous block
            nonce: Nonce value
            merkle_root: Merkle root of the events (optional, calculated if None)
        """
        self.index = index
        self.timestamp = timestamp or time.time()
        self.previous_hash = previous_hash
        self.nonce = nonce
        
        # Handle events based on input type
        if isinstance(events, pa.Table):
            self._events = events
            if merkle_root is None:
                events_list = self._table_to_list_of_dicts(self._events)
                self.merkle_root = self.calculate_merkle_from_list(events_list)
            else:
                self.merkle_root = merkle_root
        else:
            # 1. Calculate Merkle Root directly from List (avoiding Arrow conversion overhead)
            self.merkle_root = merkle_root or self.calculate_merkle_from_list(events)
            
            # 2. Convert to Arrow Table ONCE for efficient storage
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
        
        # Pre-process details to match Map<String, String> schema
        processed_events = []
        for e in events_list:
            ev = e.copy()
            details = ev.get('details')
            if isinstance(details, dict):
                ev['details'] = [(k, str(v)) for k, v in details.items()]
            elif details is None:
                ev['details'] = {}
            processed_events.append(ev)
            
        s = schemas.get_event_schema()
        return pa.Table.from_pylist(processed_events, schema=s)

    @staticmethod
    def calculate_merkle_from_list(events_list: List[Dict[str, Any]]) -> str:
        """
        Calculate Merkle Root from a list of event dictionaries.
        Static method to allow calculation before Block instantiation.
        """
        if not events_list:
            return MerkleTree([]).get_root()
        tree = MerkleTree(events_list)
        return tree.get_root()

    def calculate_merkle_root(self) -> str:
        """
        Calculate the Merkle Root of the block's events.
        """
        events_list = self._table_to_list_of_dicts(self._events)
        return self.calculate_merkle_from_list(events_list)

    def calculate_hash(self) -> str:
        """
        Calculate the hash of the block.
        Now uses Merkle Root in header instead of full event list.
        """
        block_header = {
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "merkle_root": self.merkle_root
        }
        
        return generate_hash(block_header)
    
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
                # Convert list of tuples back to dict
                if isinstance(row['details'], list):
                    row['details'] = dict(row['details'])
            else:
                 row['details'] = {}
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
            "merkle_root": self.merkle_root,
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
            nonce=data.get("nonce", 0),
            merkle_root=data.get("merkle_root")
        )
        return block # Hash is recalculated in init

    def __str__(self) -> str:
        """String representation of the block."""
        return f"Block(index={self.index}, events_count={len(self._events)}, hash={self.hash[:10]}...)"
    
    def __repr__(self) -> str:
        """Detailed string representation of the block."""
        return (f"Block(index={self.index}, events={len(self._events)}, "
                f"timestamp={self.timestamp}, hash={self.hash})")