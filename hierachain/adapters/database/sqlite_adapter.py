"""
SQLite Database Adapter for HieraChain Ledger.

Provides SQLite persistence for blockchain data by extending SQLBase.
Uses sqlite3 module for connection management and SQL execution.
"""

import sqlite3
import uuid
from contextlib import contextmanager

from hierachain.adapters.database.base.sql_adapter import SQLBase
from hierachain.adapters.database.sqlite_schema import init_database_schema
from hierachain.security.secure_logging import get_storage_logger

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
        self._memory_uri: str | None = None
        self._keeper_connection: sqlite3.Connection | None = None
        if database_path == ":memory:":
            self._memory_uri = f"file:hierachain-{uuid.uuid4().hex}?mode=memory&cache=shared"
            self._keeper_connection = sqlite3.connect(self._memory_uri, uri=True)
        try:
            self._init_schema()
        except Exception:
            self.close()
            raise

    @contextmanager
    def _get_connection(self):
        """Get a SQLite connection with dict-like row access and optimized settings."""
        if self._memory_uri is None:
            conn = sqlite3.connect(self.database_path)
        else:
            conn = sqlite3.connect(self._memory_uri, uri=True)
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
            init_database_schema(conn.cursor())
            conn.commit()

    def close(self) -> None:
        """Close the keeper connection that anchors a shared in-memory database."""
        if self._keeper_connection is not None:
            self._keeper_connection.close()
            self._keeper_connection = None

    def __str__(self) -> str:
        return f"SQLiteAdapter(database_path={self.database_path})"
    
    def __repr__(self) -> str:
        return f"SQLiteAdapter(database_path={self.database_path})"
