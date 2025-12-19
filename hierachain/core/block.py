"""
Block implementation for HieraChain Framework.

This module implements the Block class following the framework guidelines:
- Blocks contain multiple events, not one event per block
- Never equate a block with an entity
- Events are domain-specific operations with metadata
"""

import time
import json
import logging
from typing import Any, Optional, Union
import pyarrow as pa
import pyarrow.compute as pc

from hierachain.core import schemas
from hierachain.core.utils import MerkleTree, generate_hash

logger = logging.getLogger(__name__)


class Block:
    """
    Block class using Apache Arrow for high-performance event storage.
    
    Data Consistency:
    - Events are stored internally as a `pyarrow.Table`.
    - `self.events` property exposes this Table.
    - Hashing uses strict JSON canonicalization.
    """
    
    def __init__(
        self,
        index: int,
        events: Union[list[dict[str, Any]], pa.Table],
        timestamp: Optional[float] = None,
        previous_hash: str = "",
        nonce: int = 0,
        merkle_root: Optional[str] = None,
        creator_id: Optional[str] = None,
        signature: Optional[str] = None
    ):
        """
        Initialize a new block.
        
        Args:
            index: Block index in the chain
            events: List of event dicts OR an existing Arrow Table
            timestamp: Block creation timestamp (defaults to current time)
            previous_hash: Hash of the previous block
            nonce: Nonce value
            merkle_root: Merkle root of the events (optional)
        """
        self.index = index
        self.timestamp = timestamp or time.time()
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.creator_id = creator_id
        self.signature = signature
        
        # Handle events based on input type
        if isinstance(events, pa.Table):
            self._events = events
            if merkle_root is None:
                events_list = self._table_to_list_of_dicts(self._events)
                self.merkle_root = self.calculate_merkle_from_list(events_list)
            else:
                self.merkle_root = merkle_root
        else:
            # Calculate Merkle Root from list
            self.merkle_root = merkle_root or self.calculate_merkle_from_list(events)
            # Convert to Arrow Table for efficient storage
            self._events = self._convert_events_to_arrow(events)
            
        self.hash = self.calculate_hash()
    
    @property
    def events(self) -> pa.Table:
        """Access events as an Arrow Table."""
        return self._events

    @staticmethod
    def _convert_events_to_arrow(events_list: list[dict[str, Any]]) -> pa.Table:
        """
        Convert list of dicts to Arrow Table.
        
        Handles:
        - details: dict -> list of tuples for Map<String, String>
        - data: full payload as binary JSON
        """
        if not events_list:
            return pa.Table.from_pylist([], schema=schemas.get_event_schema())
        
        processed_events = []
        for e in events_list:
            ev = e.copy()
            
            # Process details field
            details = ev.get('details')
            if isinstance(details, dict):
                # Convert dict to list of tuples, stringify values
                ev['details'] = [(k, str(v)) for k, v in details.items()]
            elif isinstance(details, list):
                # Already list of tuples - keep as is
                ev['details'] = details
            elif details is None:
                ev['details'] = []

            # Store full payload as binary JSON
            clean_event = {}
            for k, v in e.items():
                if isinstance(v, bytes) or k == 'data':
                    continue
                if k == 'details' and isinstance(v, list):
                    try:
                        clean_event[k] = dict(v)
                    except (TypeError, ValueError):
                        clean_event[k] = v
                else:
                    clean_event[k] = v
            ev['data'] = json.dumps(clean_event).encode('utf-8')

            processed_events.append(ev)
            
        return pa.Table.from_pylist(processed_events, schema=schemas.get_event_schema())

    @staticmethod
    def calculate_merkle_from_list(events_list: list[dict[str, Any]]) -> str:
        """Calculate Merkle Root from a list of event dictionaries."""
        if not events_list:
            return MerkleTree([]).get_root()
        tree = MerkleTree(events_list)
        return tree.get_root()

    def calculate_merkle_root(self) -> str:
        """Calculate the Merkle Root of the block's events."""
        events_list = self._table_to_list_of_dicts(self._events)
        return self.calculate_merkle_from_list(events_list)

    def calculate_hash(self) -> str:
        """Calculate the hash of the block."""
        block_header = {
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "merkle_root": self.merkle_root,
            "creator_id": self.creator_id
        }
        
        return generate_hash(block_header)
    
    def get_events_by_entity(self, entity_id: str) -> list[dict[str, Any]]:
        """Get all events for a specific entity using Arrow filtering."""
        filtered = self._events.filter(pc.equal(self._events['entity_id'], entity_id))
        return self._table_to_list_of_dicts(filtered)

    def get_events_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Get all events of a specific type."""
        filtered = self._events.filter(pc.equal(self._events['event'], event_type))
        return self._table_to_list_of_dicts(filtered)
    
    def to_event_list(self) -> list[dict[str, Any]]:
        """Convert internal Arrow events to a list of dictionaries."""
        return self._table_to_list_of_dicts(self._events)

    @staticmethod
    def _table_to_list_of_dicts(table: pa.Table) -> list[dict[str, Any]]:
        """
        Convert Arrow Table to list of dicts with parsed details.
        
        Uses 'data' field for full payload recovery when available.
        """
        events = []
        has_data_col = 'data' in table.column_names

        for row in table.to_pylist():
            # 1. Try to recover full object from 'data' payload
            if has_data_col and row.get('data'):
                try:
                    event_data = json.loads(row['data'])
                    events.append(event_data)
                    continue
                except (json.JSONDecodeError, TypeError) as e:
                    logger.debug(f"JSON decode fallback: {e}")
            
            # 2. Fallback: Reconstruct from flat schema
            if row.get('details'):
                if isinstance(row['details'], list):
                    row['details'] = dict(row['details'])
            else:
                row['details'] = {}
            
            # Remove internal 'data' field from output
            if 'data' in row:
                del row['data']
                
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
    
    def to_dict(self) -> dict[str, Any]:
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
            "hash": self.hash,
            "creator_id": self.creator_id,
            "signature": self.signature
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Block':
        """
        Create a Block instance from dictionary data.

        Args:
            data: Dictionary containing block data

        Returns:
            Block instance
        """
        return cls(
            index=data["index"],
            events=data["events"],
            timestamp=data["timestamp"],
            previous_hash=data["previous_hash"],
            nonce=data.get("nonce", 0),
            merkle_root=data.get("merkle_root"),
            creator_id=data.get("creator_id"),
            signature=data.get("signature")
        )

    def __str__(self) -> str:
        """String representation of the block."""
        return f"Block(index={self.index}, events={len(self._events)}, hash={self.hash[:10]}...)"
    
    def __repr__(self) -> str:
        """Detailed string representation of the block."""
        return f"Block(index={self.index}, events={len(self._events)}, hash={self.hash})"