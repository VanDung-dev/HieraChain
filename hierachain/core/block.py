"""
Block implementation for HieraChain Ledger.

This module implements the Block class following the Ledger guidelines:
- Blocks contain multiple events, not one event per block
- Never equate a block with an entity
- Events are domain-specific operations with metadata
"""

import time
import hashlib
import logging
from typing import Any
import pyarrow as pa
import pyarrow.compute as pc
import orjson

from hierachain.core import schemas
from hierachain.core.utils import generate_hash
from hierachain.core.merkle_tree import MerkleTree


logger = logging.getLogger(__name__)


class Block:
    """
    Block class using Apache Arrow for high-performance event storage.

    Data Consistency:
    - Events are stored internally as a `pyarrow.Table`.
    - `self.events` property exposes this Table.
    - Hashing uses strict JSON canonicalization.
    """
    __slots__ = (
        'index', 'timestamp', 'previous_hash', 'nonce',
        'merkle_root', 'creator_id', 'signature', '_events', 'hash',
    )

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
        self.index = index
        self.timestamp = timestamp or time.time()
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.creator_id = creator_id
        self.signature = signature

        # Handle events based on input type
        if isinstance(events, pa.Table):
            self._events = events
            self.merkle_root = merkle_root if merkle_root is not None else calculate_merkle_from_arrow(self._events)
        else:
            if merkle_root is not None:
                self.merkle_root = merkle_root
                self._events = convert_events_to_arrow(events)
            else:
                processed, data_list = _prepare_events(events)
                self.merkle_root = calculate_merkle_from_data(data_list)
                self._events = _build_arrow_from_processed(processed)

        self.hash = self.calculate_hash()

    @property
    def events(self) -> pa.Table:
        """Access events as an Arrow Table."""
        return self._events

    def calculate_merkle_root(self) -> str:
        """Calculate the Merkle Root of the block's events."""
        return calculate_merkle_from_arrow(self._events)

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
        block = cls(
            index=data["index"],
            events=data["events"],
            timestamp=data["timestamp"],
            previous_hash=data["previous_hash"],
            nonce=data.get("nonce", 0),
            merkle_root=data.get("merkle_root"),
            creator_id=data.get("creator_id"),
            signature=data.get("signature")
        )
        # Verify integrity: recalculate hash and compare with stored hash
        stored_hash = data.get("hash")
        if stored_hash is not None and block.hash != stored_hash:
            raise ValueError(
                f"Block hash MISMATCH! index={block.index} "
                f"stored={stored_hash[:16]} computed={block.hash[:16]}"
            )
        return block

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
    return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)


def _convert_events_to_arrow(events_list: list[dict[str, Any]]) -> pa.Table:
    """Convert list of dicts to Arrow Table."""
    processed, _ = _prepare_events(events_list)
    return _build_arrow_from_processed(processed)


def convert_events_to_arrow(events_list: list[dict[str, Any]]) -> pa.Table:
    """Convert list of dicts to Arrow Table."""
    return _convert_events_to_arrow(events_list)


def _prepare_events(events_list: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[bytes]]:
    """Pre-process events: compute data bytes + Arrow-friendly details. Returns (processed_events, data_bytes)."""
    processed = []
    data_list = []
    for e in events_list:
        ev = e.copy()
        ev['details'] = _process_event_details(ev.get('details'))
        data = _serialize_event_payload(e)
        ev['data'] = data
        processed.append(ev)
        data_list.append(data)
    return processed, data_list


def _build_arrow_from_processed(processed_events: list[dict[str, Any]]) -> pa.Table:
    """Build Arrow table from pre-processed event dicts (avoids re-serialization)."""
    schema = schemas.get_event_schema()
    if not processed_events:
        return pa.table({name: [] for name in schema.names}, schema=schema)
    pydict = {
        name: [row.get(name) for row in processed_events]
        for name in schema.names
    }
    return pa.table(pydict, schema=schema)


def calculate_merkle_from_data(data_list: list[bytes]) -> str:
    """Compute Merkle root from pre-serialized data bytes (no double JSON encoding)."""
    if not data_list:
        return MerkleTree([]).get_root()
    leaves = [hashlib.sha256(d).hexdigest() for d in data_list]
    return MerkleTree(leaves=leaves).get_root()


def calculate_merkle_from_arrow(table: pa.Table) -> str:
    """Compute Merkle root directly from Arrow table's pre-serialized data column."""
    if 'data' in table.column_names:
        data_list = table.column('data').to_pylist()
        return calculate_merkle_from_data(data_list)
    return calculate_merkle_from_list(table_to_list_of_dicts(table))


def calculate_merkle_from_list(events_list: list[dict[str, Any]]) -> str:
    """Calculate Merkle Root from a list of event dictionaries."""
    if not events_list:
        return MerkleTree([]).get_root()
    tree = MerkleTree(events_list)
    return tree.get_root()


def _recover_from_data_column(row: dict[str, Any]) -> dict[str, Any] | None:
    """Try to recover full event object from binary data column."""
    data = row.get('data')
    if not isinstance(data, (str, bytes, bytearray)):
        return None
    try:
        return orjson.loads(data)
    except (ValueError, TypeError) as e:
        logger.debug("JSON decode fallback: %s", e)
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
