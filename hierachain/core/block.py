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
from typing import Any
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
        events: list[dict[str, Any]] | pa.Table,
        timestamp: float | None = None,
        previous_hash: str = "",
        nonce: int = 0,
        merkle_root: str | None = None,
        creator_id: str | None = None,
        signature: str | None = None
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
                events_list = table_to_list_of_dicts(self._events)
                self.merkle_root = calculate_merkle_from_list(events_list)
            else:
                self.merkle_root = merkle_root
        else:
            # Calculate Merkle Root from list
            self.merkle_root = merkle_root or calculate_merkle_from_list(events)
            # Convert to Arrow Table for efficient storage
            self._events = _convert_events_to_arrow(events)
            
        self.hash = self.calculate_hash()

    @property
    def events(self) -> pa.Table:
        """Access events as an Arrow Table."""
        return self._events

    def calculate_merkle_root(self) -> str:
        """Calculate the Merkle Root of the block's events."""
        events_list = table_to_list_of_dicts(self._events)
        return calculate_merkle_from_list(events_list)

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
        filtered = self._events.filter(pc.field("entity_id") == entity_id)
        return table_to_list_of_dicts(filtered)

    def get_events_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Get all events of a specific type."""
        filtered = self._events.filter(pc.field("event") == event_type)
        return table_to_list_of_dicts(filtered)

    def to_event_list(self) -> list[dict[str, Any]]:
        """Convert internal Arrow events to a list of dictionaries."""
        return table_to_list_of_dicts(self._events)

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
            "events": table_to_list_of_dicts(self._events),
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
        return (
            f"Block(index={self.index}, "
            f"events={len(self._events)}, "
            f"hash={self.hash[:10]}...)"
        )

    def __repr__(self) -> str:
        """Detailed string representation of the block."""
        return (
            f"Block(index={self.index}, "
            f"events={len(self._events)}, "
            f"hash={self.hash})"
        )


def _process_event_details(details: Any) -> list[tuple[str, str]]:
    """Process details field for Arrow Map<String, String> conversion."""
    if isinstance(details, dict):
        return [(k, str(v)) for k, v in details.items()]
    if isinstance(details, list):
        return details
    return []


def _should_exclude_from_payload(key: str, value: Any) -> bool:
    """Check if a field should be excluded from the JSON payload."""
    return isinstance(value, (bytes, bytearray)) or key == 'data'


def _prepare_payload_value(key: str, value: Any) -> Any:
    """Prepare a value for JSON serialization."""
    if key == 'details' and isinstance(value, list):
        try:
            return dict(value)
        except (TypeError, ValueError):
            return value
    return value


def _serialize_event_payload(event: dict[str, Any]) -> bytes:
    """Serialize the event payload to binary JSON, cleaning binary/data fields."""
    payload = {
        k: _prepare_payload_value(k, v)
        for k, v in event.items()
        if not _should_exclude_from_payload(k, v)
    }
    return json.dumps(payload).encode('utf-8')


def _convert_events_to_arrow(events_list: list[dict[str, Any]]) -> pa.Table:
    """
    Convert list of dicts to Arrow Table.

    Handles:
    - details: dict -> list of tuples for Map<String, String>
    - data: full payload as binary JSON
    """
    schema = schemas.get_event_schema()
    if not events_list:
        return pa.table({name: [] for name in schema.names}, schema=schema)

    processed_events = []
    for e in events_list:
        ev = e.copy()
        # Process fields for Arrow storage
        ev['details'] = _process_event_details(ev.get('details'))
        ev['data'] = _serialize_event_payload(e)
        processed_events.append(ev)

    pydict = {
        name: [row.get(name) for row in processed_events]
        for name in schema.names
    }
    return pa.table(pydict, schema=schema)


def calculate_merkle_from_list(events_list: list[dict[str, Any]]) -> str:
    """Calculate Merkle Root from a list of event dictionaries."""
    if not events_list:
        return MerkleTree([]).get_root()
    tree = MerkleTree(events_list)
    return tree.get_root()


def _recover_from_data_column(row: dict[str, Any]) -> dict[str, Any] | None:
    """Try to recover full event object from binary data column."""
    data = row.get('data')
    if not data:
        return None
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as e:
        logger.debug(f"JSON decode fallback: {e}")
        return None


def _reconstruct_from_flat_schema(row: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct event object from flat schema columns."""
    res = row.copy()
    details = res.get('details')
    res['details'] = dict(details) if isinstance(details, list) else (details or {})

    # Remove internal 'data' field from output
    res.pop('data', None)
    return res


def _process_arrow_row(row: dict[str, Any], has_data_col: bool) -> dict[str, Any]:
    """Process a single Arrow row, recovering full payload or reconstructing details."""
    if has_data_col:
        recovered = _recover_from_data_column(row)
        if recovered is not None:
            return recovered

    return _reconstruct_from_flat_schema(row)


def table_to_list_of_dicts(table: pa.Table) -> list[dict[str, Any]]:
    """
    Convert Arrow Table to list of dicts with parsed details.

    Uses 'data' field for full payload recovery when available.
    """
    has_data_col = 'data' in table.column_names
    return [_process_arrow_row(row, has_data_col) for row in table.to_pylist()]
