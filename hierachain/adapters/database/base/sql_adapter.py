"""
SQL Adapter Base for HieraChain Ledger.

This module provides the abstract base class for all SQL database adapters.
Subclasses must implement:
- _get_connection(): context manager yielding a DB-API connection
- _init_schema(): create tables and indexes

Template method pattern:
- Public methods (store_chain, load_chain, etc.) are in the base class
- Each calls a corresponding _execute_* method with DB-specific SQL
- Default _execute_* implementations use SQLite-compatible dialect
- Override specific _execute_* methods for other DB dialects (MySQL, PostgreSQL, etc.)
"""

from abc import ABC, abstractmethod
import orjson
import time
from typing import Any, Callable
from contextlib import contextmanager

from hierachain.core.blockchain import Blockchain
from hierachain.security.secure_logging import get_storage_logger
from hierachain.config.settings import settings


class SQLBase(ABC):
    """
    Abstract base class for SQL database adapters.

    Default implementations use SQLite-compatible SQL dialect (?, :name placeholders).
    Subclasses override specific _execute_* methods for DB-specific SQL.
    """

    logger = get_storage_logger()

    @abstractmethod
    @contextmanager
    def _get_connection(self):
        """Context manager yielding a database connection."""
        ...

    @abstractmethod
    def _init_schema(self) -> None:
        """Create database tables and indexes."""
        ...

    # --- Shared pure-Python utilities ---

    def _execute_with_error_handling(self, operation: str, func: Callable, **context) -> Any:
        """Execute a database operation with standardized error handling."""
        try:
            return func()
        except Exception as e:
            self.logger.error("Database operation failed", operation=operation, **context)
            if settings.LOG_SQL_DETAIL:
                self.logger.debug(
                    "Database operation error detail", error_type=type(e).__name__
                )
            return None

    @staticmethod
    def _determine_chain_type(chain: Blockchain) -> str:
        """Determine if chain is main or sub chain."""
        return "main" if "MainChain" in str(type(chain)) else "sub"

    @staticmethod
    def _create_block_data(block_row: Any, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Create block data dictionary from database row and events."""
        return {
            "index": block_row['index'],
            "events": events,
            "timestamp": block_row['timestamp'],
            "previous_hash": block_row['previous_hash'],
            "nonce": block_row['nonce'],
            "hash": block_row['hash'],
        }

    @staticmethod
    def _create_event_from_row(row: Any) -> dict[str, Any]:
        """Create event dictionary from a database row."""
        return {
            "chain_name": row["chain_name"],
            "entity_id": row["entity_id"],
            "event_type": row["event_type"],
            "timestamp": row["timestamp"],
            "data": orjson.loads(row["data"] or "{}"),
        }

    # --- Template: store_chain ---

    def store_chain(self, chain: Blockchain) -> bool:
        """Store a blockchain in the database."""
        def _op():
            with self._get_connection() as conn:
                return self._execute_store_chain(conn, chain)
        result = self._execute_with_error_handling(
            "store_chain", _op, chain_name=chain.name
        )
        return result if result is not None else False

    def _execute_store_chain(self, conn: Any, chain: Blockchain) -> bool:
        """Default SQLite implementation. Override for DB-specific SQL dialect."""
        cursor = conn.cursor()
        chain_type = self._determine_chain_type(chain)
        domain_type = getattr(chain, 'domain_type', None)
        cursor.execute(
            """
            INSERT OR REPLACE INTO chains
            (name, chain_type, domain_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chain.name, chain_type, domain_type, time.time(), time.time()),
        )
        conn.commit()
        return True

    # --- Template: load_chain ---

    def load_chain(self, chain_name: str) -> dict[str, Any] | None:
        """Load a blockchain from the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                chain_row = self._execute_fetch_chain_info(cursor, chain_name)
                if not chain_row:
                    return None
                blocks = self._execute_fetch_blocks_with_events(cursor, chain_name)
                return {
                    "name": chain_row['name'],
                    "chain_type": chain_row['chain_type'],
                    "domain_type": chain_row['domain_type'],
                    "chain": blocks,
                    "pending_events": [],
                }
        except Exception as e:
            self.logger.error(
                "Database operation failed",
                operation="load_chain",
                chain_name=chain_name,
            )
            if settings.LOG_SQL_DETAIL:
                self.logger.debug("Load chain error detail", error_type=type(e).__name__)
            return None

    @staticmethod
    def _execute_fetch_chain_info(cursor: Any, chain_name: str) -> Any | None:
        """Default SQLite implementation."""
        cursor.execute("SELECT * FROM chains WHERE name = ?", (chain_name,))
        return cursor.fetchone()

    def _execute_fetch_blocks_with_events(
        self, cursor: Any, chain_name: str,
    ) -> list[dict[str, Any]]:
        """Default SQLite implementation."""
        block_rows = self._execute_fetch_block_rows(cursor, chain_name)
        blocks = []
        for block_row in block_rows:
            events = self._execute_fetch_block_events(cursor, block_row['hash'])
            block_data = self._create_block_data(block_row, events)
            blocks.append(block_data)
        return blocks

    @staticmethod
    def _execute_fetch_block_rows(cursor: Any, chain_name: str) -> list[Any]:
        """Default SQLite implementation."""
        cursor.execute(
            """SELECT * FROM blocks WHERE chain_name = ? ORDER BY "index" """,
            (chain_name,),
        )
        return cursor.fetchall()

    def _execute_fetch_block_events(self, cursor: Any, block_hash: str) -> list[dict[str, Any]]:
        """Default SQLite implementation."""
        cursor.execute(
            """
            SELECT entity_id, event_type, timestamp, data
            FROM events WHERE block_hash = ? ORDER BY id
            """,
            (block_hash,),
        )
        return [self._create_event_from_row(row) for row in cursor.fetchall()]

    # --- Template: events filter ---

    _FILTER_COLUMNS = {
        "chain_name": "chain_name",
        "event_type": "event_type",
        "entity_id": "entity_id",
        "timestamp": "timestamp",
    }

    def _get_events_by_filter(
        self, filter_field: str, filter_value: str,
        chain_name: str | None, operation_name: str,
    ) -> list[dict[str, Any]]:
        """Get events by filtering on a specific field."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if filter_field not in self._FILTER_COLUMNS:
                    self.logger.warning("Invalid filter field", filter_field=filter_field)
                    return []
                return self._execute_query_events_filter(
                    cursor, self._FILTER_COLUMNS[filter_field],
                    filter_value, chain_name,
                )
        except Exception as e:
            self.logger.error(
                "Database operation failed",
                operation=operation_name,
                **{filter_field: filter_value},
            )
            if settings.LOG_SQL_DETAIL:
                self.logger.debug(
                    "Get events by filter error detail", error_type=type(e).__name__
                )
            return []

    def _execute_query_events_filter(
        self, cursor: Any, filter_column: str,
        filter_value: str, chain_name: str | None,
    ) -> list[dict[str, Any]]:
        """Default SQLite implementation."""
        if chain_name:
            query = (
                """
                SELECT chain_name, block_index, entity_id, event_type, timestamp, details
                FROM events WHERE chain_name = :cn AND {col} = :fv
                ORDER BY timestamp
                """.replace("{col}", filter_column)
            )
            cursor.execute(query, {"cn": chain_name, "fv": filter_value})
        else:
            query = (
                """
                SELECT chain_name, block_index, entity_id, event_type, timestamp, details
                FROM events WHERE {col} = :fv
                ORDER BY timestamp
                """.replace("{col}", filter_column)
            )
            cursor.execute(query, {"fv": filter_value})
        return [self._create_event_from_row(row) for row in cursor.fetchall()]

    # --- Template: store_proof ---

    def store_proof(
        self,
        main_chain_name: str,
        sub_chain_name: str,
        proof_hash: str,
        block_index: int,
        metadata: dict[str, Any],
    ) -> bool:
        """Store a proof submission from Sub-Chain to Main Chain."""
        def _op():
            with self._get_connection() as conn:
                return self._execute_store_proof(
                    conn, main_chain_name, sub_chain_name,
                    proof_hash, block_index, metadata,
                )
        result = self._execute_with_error_handling("store_proof", _op)
        return result if result is not None else False

    @staticmethod
    def _execute_store_proof(
            conn: Any,
        main_chain_name: str, sub_chain_name: str,
        proof_hash: str, block_index: int,
        metadata: dict[str, Any],
    ) -> bool:
        """Default SQLite implementation."""
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO proofs
            (main_chain_name, sub_chain_name, proof_hash, block_index, metadata, submitted_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                main_chain_name,
                sub_chain_name,
                proof_hash,
                block_index,
                orjson.dumps(metadata).decode('utf-8'),
                time.time(),
                time.time(),
            ),
        )
        conn.commit()
        return True

    # --- Public API: get_entity_events, get_events_by_type ---

    def get_entity_events(
        self, entity_id: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all events for a specific entity."""
        return self._get_events_by_filter(
            "entity_id", entity_id, chain_name, "get_entity_events",
        )

    def get_events_by_type(
        self, event_type: str, chain_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all events of a specific type."""
        return self._get_events_by_filter(
            "event_type", event_type, chain_name, "get_events_by_type",
        )

    # --- Template: get_chain_statistics ---

    def get_chain_statistics(self, chain_name: str) -> dict[str, Any]:
        """Get statistics for a specific chain."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                return self._execute_chain_statistics(cursor, chain_name)
        except Exception as e:
            self.logger.error(
                "Database operation failed",
                operation="get_chain_statistics",
                chain_name=chain_name,
            )
            if settings.LOG_SQL_DETAIL:
                self.logger.debug(
                    "Get chain statistics error detail", error_type=type(e).__name__
                )
            return {}

    @staticmethod
    def _execute_chain_statistics(cursor: Any, chain_name: str) -> dict[str, Any]:
        """Default SQLite implementation."""
        cursor.execute("SELECT * FROM chains WHERE name = ?", (chain_name,))
        chain_row = cursor.fetchone()
        if not chain_row:
            return {}

        cursor.execute(
            "SELECT COUNT(*) as block_count FROM blocks WHERE chain_name = ?",
            (chain_name,),
        )
        block_count = cursor.fetchone()['block_count']

        cursor.execute(
            "SELECT COUNT(*) as event_count FROM events WHERE chain_name = ?",
            (chain_name,),
        )
        event_count = cursor.fetchone()['event_count']

        cursor.execute(
            """
            SELECT COUNT(DISTINCT entity_id) as entity_count
            FROM events WHERE chain_name = ? AND entity_id IS NOT NULL
            """,
            (chain_name,),
        )
        entity_count = cursor.fetchone()['entity_count']

        cursor.execute(
            """
            SELECT event_type, COUNT(*) as count
            FROM events WHERE chain_name = ?
            GROUP BY event_type ORDER BY count DESC
            """,
            (chain_name,),
        )
        event_types = {
            row['event_type']: row['count'] for row in cursor.fetchall()
        }

        return {
            "chain_name": chain_name,
            "chain_type": chain_row['chain_type'],
            "domain_type": chain_row['domain_type'],
            "total_blocks": block_count,
            "total_events": event_count,
            "unique_entities": entity_count,
            "event_types": event_types,
            "created_at": chain_row['created_at'],
            "updated_at": chain_row['updated_at'],
        }

    # --- Template: get_proof_history ---

    def get_proof_history(self, sub_chain_name: str) -> list[dict[str, Any]]:
        """Get proof submission history for a Sub-Chain."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                return self._execute_get_proof_history(cursor, sub_chain_name)
        except Exception as e:
            self.logger.error(
                "Database operation failed",
                operation="get_proof_history",
                sub_chain_name=sub_chain_name,
            )
            if settings.LOG_SQL_DETAIL:
                self.logger.debug(
                    "Get proof history error detail", error_type=type(e).__name__
                )
            return []

    @staticmethod
    def _execute_get_proof_history(
            cursor: Any, sub_chain_name: str,
    ) -> list[dict[str, Any]]:
        """Default SQLite implementation."""
        cursor.execute(
            """
            SELECT main_chain_name, sub_chain_name, proof_hash, block_index, metadata, submitted_at
            FROM proofs WHERE sub_chain_name = ?
            ORDER BY submitted_at DESC
            """,
            (sub_chain_name,),
        )
        proofs = []
        for row in cursor.fetchall():
            proofs.append({
                "main_chain_name": row['main_chain_name'],
                "sub_chain_name": row['sub_chain_name'],
                "proof_hash": row['proof_hash'],
                "block_index": row['block_index'],
                "metadata": orjson.loads(row['metadata'] or '{}'),
                "submitted_at": row['submitted_at'],
            })
        return proofs

    # --- Template: cleanup_old_data ---

    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        """Clean up old data from the database."""
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                self._execute_cleanup(cursor, cutoff_time)
                conn.commit()
                return True
        except Exception as e:
            self.logger.error("Database operation failed", operation="cleanup")
            if settings.LOG_SQL_DETAIL:
                self.logger.debug("Cleanup error detail", error_type=type(e).__name__)
            return False

    def _execute_cleanup(self, cursor: Any, cutoff_time: float) -> None:
        """Default SQLite implementation."""
        cursor.execute("DELETE FROM events WHERE created_at < ?", (cutoff_time,))
        events_deleted = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM blocks WHERE id NOT IN (
                SELECT DISTINCT block_id FROM events
            ) AND created_at < ?
            """,
            (cutoff_time,),
        )
        blocks_deleted = cursor.rowcount

        cursor.execute("DELETE FROM proofs WHERE created_at < ?", (cutoff_time,))
        proofs_deleted = cursor.rowcount

        self.logger.info(
            "Cleanup completed",
            events_deleted=events_deleted,
            blocks_deleted=blocks_deleted,
            proofs_deleted=proofs_deleted,
        )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}()"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
