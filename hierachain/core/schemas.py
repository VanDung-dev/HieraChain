"""
Arrow Schemas for HieraChain Core Data Structures.

This module defines the Apache Arrow schemas used for events.
"""

import pyarrow as pa

EVENT_SCHEMA = pa.schema([
    ('entity_id', pa.string()),
    ('event', pa.string()),
    ('timestamp', pa.float64()),
    ('details', pa.map_(pa.string(), pa.string())),
    ('details_cid', pa.string()),
    ('details_nonce', pa.string()),
    ('data', pa.binary()),
])


def get_event_schema() -> pa.Schema:
    """Return the Arrow schema for an Event."""
    return EVENT_SCHEMA


SERIALIZATION_METADATA_KEY = b'hiera_metadata'
