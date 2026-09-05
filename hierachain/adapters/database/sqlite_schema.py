"""
SQLite database schema definitions for HieraChain Ledger.

This module contains all DDL statements for creating tables and indexes
used by the SQLite adapter.
"""

import sqlite3


def create_chains_table(cursor: sqlite3.Cursor) -> None:
    """Create chains table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            chain_type TEXT NOT NULL,  -- 'main' or 'sub'
            domain_type TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )


def create_blocks_table(cursor: sqlite3.Cursor) -> None:
    """Create blocks table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain_name TEXT NOT NULL,
            "index" INTEGER NOT NULL,
            hash TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            timestamp REAL NOT NULL,
            nonce INTEGER DEFAULT 0,
            events_count INTEGER DEFAULT 0,
            metadata_json JSON,
            created_at REAL DEFAULT (unixepoch()),
            FOREIGN KEY (chain_name) REFERENCES chains (name),
            UNIQUE (chain_name, "index"),
            UNIQUE (hash)
        )
        """
    )


def create_events_table(cursor: sqlite3.Cursor) -> None:
    """Create events table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain_name TEXT NOT NULL,
            block_hash TEXT NOT NULL,
            event_id TEXT,
            entity_id TEXT,  -- Metadata field, not identifier
            event_type TEXT NOT NULL,
            timestamp REAL NOT NULL,
            data JSON,  -- JSON string
            sender_id TEXT,
            created_at REAL DEFAULT (unixepoch()),
            FOREIGN KEY (chain_name) REFERENCES chains (name),
            FOREIGN KEY (block_hash) REFERENCES blocks (hash)
        )
        """
    )


def create_proofs_table(cursor: sqlite3.Cursor) -> None:
    """Create proofs table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS proofs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_chain_name TEXT NOT NULL,
            sub_chain_name TEXT NOT NULL,
            proof_hash TEXT NOT NULL,
            block_index INTEGER NOT NULL,
            metadata TEXT,  -- JSON string with summary data only
            submitted_at REAL NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (main_chain_name) REFERENCES chains (name),
            FOREIGN KEY (sub_chain_name) REFERENCES chains (name)
        )
        """
    )


def create_indexes(cursor: sqlite3.Cursor) -> None:
    """Create database indexes for efficient querying."""
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_events_entity_id ON events (entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type)",
        "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_events_chain ON events (chain_name)",
        "CREATE INDEX IF NOT EXISTS idx_events_event_id ON events (event_id)",
        "CREATE INDEX IF NOT EXISTS idx_blocks_hash_val ON blocks (hash)",
        "CREATE INDEX IF NOT EXISTS idx_blocks_chain ON blocks (chain_name)",
        "CREATE INDEX IF NOT EXISTS idx_proofs_sub_chain ON proofs (sub_chain_name)",
    ]

    for stmt in index_statements:
        cursor.execute(stmt)


def create_chain_state_table(cursor: sqlite3.Cursor) -> None:
    """Create chain_state key-value table for quick state lookups."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chain_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,  -- JSON string
            last_block_hash TEXT,
            updated_at REAL DEFAULT (unixepoch())
        )
        """
    )


def init_database_schema(cursor: sqlite3.Cursor) -> None:
    """Create all SQLite database tables and indexes."""
    create_chains_table(cursor)
    create_blocks_table(cursor)
    create_events_table(cursor)
    create_proofs_table(cursor)
    create_chain_state_table(cursor)
    create_indexes(cursor)
