"""
Arrow Schemas for HieraChain Core Data Structures.

This module defines the Apache Arrow schemas used for:
- Events: Domain-specific actions
- Blocks: Groups of events
- BlockHeaders: Metadata for blocks
"""

import pyarrow as pa


# Event Schema
# Corresponds to a single event dictionary
EVENT_SCHEMA = pa.schema([
    ('entity_id', pa.string()),      # Metadata: Unique ID of the entity
    ('event', pa.string()),          # Event type
    ('timestamp', pa.float64()),     # Event timestamp
    ('details', pa.string())         # Flexible details (JSON string)
])


# Block Header Schema (for metadata only, if needed separately)
BLOCK_HEADER_SCHEMA = pa.schema([
    ('index', pa.int64()),
    ('timestamp', pa.float64()),
    ('previous_hash', pa.string()),
    ('nonce', pa.int64()),
    ('hash', pa.string())
])


def get_event_schema() -> pa.Schema:
    """Return the Arrow schema for an Event."""
    return EVENT_SCHEMA


def get_block_schema() -> pa.Schema:
    """Return the Arrow schema for a full Block (header + events)."""
    return pa.schema([
        ('index', pa.int64()),               # Block index
        ('timestamp', pa.float64()),         # Block timestamp
        ('previous_hash', pa.string()),      # Hash of the previous block
        ('nonce', pa.int64()),               # Nonce for mining
        ('timestamp', pa.float64()),         # Block timestamp
        ('previous_hash', pa.string()),      # Hash of the previous block
        ('nonce', pa.int64()),               # Nonce for mining
        ('hash', pa.string()),               # Hash of the block
        ('events', pa.list_(pa.struct([      # List of events:
            ('entity_id', pa.string()),         # Renamed from entity_id to match EVENT_SCHEMA
            ('event', pa.string()),             # Renamed from event_type to match EVENT_SCHEMA
            ('timestamp', pa.float64()),        # Renamed from timestamp to match EVENT_SCHEMA
            ('details', pa.string())            # Renamed from details to match EVENT_SCHEMA
        ])))
    ])

# Constants for conversion
SERIALIZATION_METADATA_KEY = b'hiera_metadata'
