"""
Helper functions for SQLite database operations in HieraChain Ledger.

This module provides shared utility functions used by SQLiteAdapter
for block and event record manipulation.
"""

import json
import sqlite3
import time
from typing import Any

from hierachain.core.block import Block, table_to_list_of_dicts


def extract_entity_id(event: Any) -> str | None:
    """Extract entity_id from event data if available."""
    if not hasattr(event, "data") or not isinstance(event.data, dict):
        return None

    entity_id = event.data.get("entity_id")
    if not entity_id and "product_id" in event.data:
        entity_id = event.data.get("product_id")
    return entity_id


def insert_block_record(cursor: sqlite3.Cursor, chain_name: str, block: Block) -> None:
    """Insert or replace a block record in the database."""
    metadata_json = json.dumps(block.metadata) if hasattr(block, "metadata") else None

    cursor.execute(
        """
        INSERT OR REPLACE INTO blocks
        (chain_name, "index", hash, previous_hash, timestamp, nonce, events_count, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chain_name,
            block.index,
            block.hash,
            block.previous_hash,
            block.timestamp,
            block.nonce,
            len(block.events),
            metadata_json,
            time.time()
        )
    )


def insert_event_records(
    cursor: sqlite3.Cursor, chain_name: str, block_hash: str, events: list[Any]
) -> None:
    """Insert events for a specific block into the database."""
    for event in events:
        entity_id = extract_entity_id(event)
        event_data_json = json.dumps(event.data) if hasattr(event, "data") else "{}"

        cursor.execute(
            """
            INSERT OR IGNORE INTO events
            (chain_name, block_hash, event_id, entity_id, event_type, timestamp, data, sender_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                chain_name,
                block_hash,
                getattr(event, "event_id", None),
                entity_id,
                event.event_type,
                event.timestamp,
                event_data_json,
                getattr(event, "sender_id", None)
            )
        )


def store_block(cursor: sqlite3.Cursor, chain_name: str, block: Block) -> None:
    """Store a single block and its events."""
    insert_block_record(cursor, chain_name, block)
    events_list = table_to_list_of_dicts(block.events)
    insert_event_records(cursor, chain_name, block.hash, events_list)


def create_event_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Create event dictionary from database row."""
    return {
        "chain_name": row["chain_name"],
        "entity_id": row["entity_id"],
        "event_type": row["event_type"],
        "timestamp": row["timestamp"],
        "data": json.loads(row["data"] or "{}")
    }
