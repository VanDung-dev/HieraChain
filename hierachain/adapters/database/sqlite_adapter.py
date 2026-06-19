"""
SQLite Database Adapter for HieraChain Ledger.

Provides SQLite persistence for blockchain data by extending SQLBase.
Uses sqlite3 module for connection management and SQL execution.
"""

import sqlite3
from contextlib import contextmanager

from hierachain.adapters.database.base.sql_adapter import SQLBase
from hierachain.security.secure_logging import get_storage_logger
from hierachain.adapters.database.sqlite_schema import (
    create_chains_table,
    create_blocks_table,
    create_events_table,
    create_proofs_table,
    create_indexes,
)

logger = get_storage_logger()


class SQLiteAdapter(SQLBase):
    """
    SQLite implementation of SQLBase adapter.
    Stores and retrieves blockchain data with event-based model.
    """

    def __init__(self, database_path: str = "hierachain.db"):
        self.database_path = database_path
        if ".." in self.database_path:
            raise ValueError(
                f"Security: Invalid database path '{self.database_path}'."
                f"Path traversal detected."
            )
        self.connection_pool_size = 5
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Get a SQLite connection with dict-like row access and optimized settings."""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            # Enable high-performance PRAGMAs
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache size
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


    def _init_schema(self) -> None:
        """Create database tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            create_chains_table(cursor)
            create_blocks_table(cursor)
            create_events_table(cursor)
            create_proofs_table(cursor)
            create_indexes(cursor)
            conn.commit()

    def __str__(self) -> str:
        return f"SQLiteAdapter(database_path={self.database_path})"
    
    def __repr__(self) -> str:
        return f"SQLiteAdapter(database_path={self.database_path})"
