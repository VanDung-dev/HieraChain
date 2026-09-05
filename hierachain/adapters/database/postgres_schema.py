"""
PostgreSQL database schema definitions for HieraChain Ledger.

This module contains all DDL statements for creating tables and composite indexes
used by the PostgreSQL adapter in production and containerized environments.
"""

from typing import Any


def create_chains_table(cursor: Any) -> None:
    """Create chains table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chains (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            chain_type VARCHAR(50) NOT NULL,  -- 'main' or 'sub'
            domain_type VARCHAR(100),
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
        """
    )


def create_blocks_table(cursor: Any) -> None:
    """Create blocks table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS blocks (
            id SERIAL PRIMARY KEY,
            chain_name VARCHAR(255) NOT NULL,
            "index" BIGINT NOT NULL,
            hash VARCHAR(128) UNIQUE NOT NULL,
            previous_hash VARCHAR(128) NOT NULL,
            timestamp DOUBLE PRECISION NOT NULL,
            nonce BIGINT DEFAULT 0,
            events_count INTEGER DEFAULT 0,
            metadata_json JSONB,
            created_at DOUBLE PRECISION DEFAULT (EXTRACT(EPOCH FROM NOW())),
            FOREIGN KEY (chain_name) REFERENCES chains (name) ON DELETE CASCADE,
            UNIQUE (chain_name, "index")
        )
        """
    )


def create_events_table(cursor: Any) -> None:
    """Create events table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            chain_name VARCHAR(255) NOT NULL,
            block_hash VARCHAR(128) NOT NULL,
            event_id VARCHAR(255),
            entity_id VARCHAR(255),
            event_type VARCHAR(100) NOT NULL,
            timestamp DOUBLE PRECISION NOT NULL,
            data JSONB,
            sender_id VARCHAR(255),
            created_at DOUBLE PRECISION DEFAULT (EXTRACT(EPOCH FROM NOW())),
            FOREIGN KEY (chain_name) REFERENCES chains (name) ON DELETE CASCADE,
            FOREIGN KEY (block_hash) REFERENCES blocks (hash) ON DELETE CASCADE
        )
        """
    )


def create_proofs_table(cursor: Any) -> None:
    """Create proofs table."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS proofs (
            id SERIAL PRIMARY KEY,
            main_chain_name VARCHAR(255) NOT NULL,
            sub_chain_name VARCHAR(255) NOT NULL,
            proof_hash VARCHAR(128) NOT NULL,
            block_index BIGINT NOT NULL,
            metadata JSONB,
            submitted_at DOUBLE PRECISION NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            FOREIGN KEY (main_chain_name) REFERENCES chains (name) ON DELETE CASCADE,
            FOREIGN KEY (sub_chain_name) REFERENCES chains (name) ON DELETE CASCADE
        )
        """
    )


def create_chain_state_table(cursor: Any) -> None:
    """Create chain_state key-value table for quick state lookups."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chain_state (
            key VARCHAR(255) PRIMARY KEY,
            value JSONB NOT NULL,
            last_block_hash VARCHAR(128),
            updated_at DOUBLE PRECISION DEFAULT (EXTRACT(EPOCH FROM NOW()))
        )
        """
    )


def create_indexes(cursor: Any) -> None:
    """Create optimized composite and single database indexes."""
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_events_chain_time ON events (chain_name, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_events_entity_chain ON events (entity_id, chain_name)",
        "CREATE INDEX IF NOT EXISTS idx_events_block_hash ON events (block_hash)",
        "CREATE INDEX IF NOT EXISTS idx_events_event_id ON events (event_id)",
        "CREATE INDEX IF NOT EXISTS idx_blocks_hash_val ON blocks (hash)",
        "CREATE INDEX IF NOT EXISTS idx_blocks_chain_idx ON blocks (chain_name, \"index\")",
        "CREATE INDEX IF NOT EXISTS idx_proofs_sub_chain ON proofs (sub_chain_name, block_index)",
    ]

    for stmt in index_statements:
        cursor.execute(stmt)


def init_database_schema(cursor: Any) -> None:
    """Create all PostgreSQL database tables and indexes."""
    create_chains_table(cursor)
    create_blocks_table(cursor)
    create_events_table(cursor)
    create_proofs_table(cursor)
    create_chain_state_table(cursor)
    create_indexes(cursor)
