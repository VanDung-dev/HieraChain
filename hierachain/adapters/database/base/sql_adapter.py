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
        metadata = {}
        try:
            raw = block_row['metadata_json']
            if raw:
                metadata = orjson.loads(raw) if isinstance(raw, (str, bytes)) else raw
        except (KeyError, IndexError, TypeError):
            pass
        merkle_root = metadata.get("merkle_root", "") if isinstance(metadata, dict) else ""
        return {
            "index": block_row['index'],
            "events": events,
            "timestamp": block_row['timestamp'],
            "previous_hash": block_row['previous_hash'],
            "nonce": block_row['nonce'],
            "hash": block_row['hash'],
            "merkle_root": merkle_root,
        }

    @staticmethod
    def _create_event_from_row(row: Any) -> dict[str, Any]:
        """Create event dictionary from a database row."""
        return {
            "chain_name": row["chain_name"],
            "entity_id": row["entity_id"],
            "event": row["event_type"],
            "timestamp": row["timestamp"],
            "data": orjson.loads(row["data"] or "{}"),
        }

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
            SELECT chain_name, entity_id, event_type, timestamp, data
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

    _QUERIES_WITH_CHAIN: dict[str, str] = {
        "chain_name": (
            "SELECT chain_name, block_index, entity_id, event_type, timestamp, details "
            "FROM events WHERE chain_name = :cn AND chain_name = :fv ORDER BY timestamp"
        ),
        "event_type": (
            "SELECT chain_name, block_index, entity_id, event_type, timestamp, details "
            "FROM events WHERE chain_name = :cn AND event_type = :fv ORDER BY timestamp"
        ),
        "entity_id": (
            "SELECT chain_name, block_index, entity_id, event_type, timestamp, details "
            "FROM events WHERE chain_name = :cn AND entity_id = :fv ORDER BY timestamp"
        ),
        "timestamp": (
            "SELECT chain_name, block_index, entity_id, event_type, timestamp, details "
            "FROM events WHERE chain_name = :cn AND timestamp = :fv ORDER BY timestamp"
        ),
    }

    _QUERIES_WITHOUT_CHAIN: dict[str, str] = {
        "chain_name": (
            "SELECT chain_name, block_index, entity_id, event_type, timestamp, details "
            "FROM events WHERE chain_name = :fv ORDER BY timestamp"
        ),
        "event_type": (
            "SELECT chain_name, block_index, entity_id, event_type, timestamp, details "
            "FROM events WHERE event_type = :fv ORDER BY timestamp"
        ),
        "entity_id": (
            "SELECT chain_name, block_index, entity_id, event_type, timestamp, details "
            "FROM events WHERE entity_id = :fv ORDER BY timestamp"
        ),
        "timestamp": (
            "SELECT chain_name, block_index, entity_id, event_type, timestamp, details "
            "FROM events WHERE timestamp = :fv ORDER BY timestamp"
        ),
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
        """Default SQLite implementation with parameterized queries."""
        if chain_name:
            query = self._QUERIES_WITH_CHAIN.get(filter_column)
            if not query:
                return []
            cursor.execute(query, {"cn": chain_name, "fv": filter_value})
        else:
            query = self._QUERIES_WITHOUT_CHAIN.get(filter_column)
            if not query:
                return []
            cursor.execute(query, {"fv": filter_value})
        return [self._create_event_from_row(row) for row in cursor.fetchall()]

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
            DELETE FROM blocks WHERE hash NOT IN (
                SELECT DISTINCT block_hash FROM events
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

    def save_block(self, block_data: dict[str, Any]) -> bool:
        """Upsert a block and its events into the database."""
        def _op():
            with self._get_connection() as conn:
                return self._execute_save_block(conn, block_data)
        result = self._execute_with_error_handling(
            "save_block", _op,
            block_index=block_data.get("index"),
            chain_name=block_data.get("chain_name"),
        )
        return result if result is not None else False

    def _execute_save_block(self, conn: Any, block_data: dict[str, Any]) -> bool:
        """Default SQLite implementation — upsert block then insert events."""
        cursor = conn.cursor()
        chain_name = str(block_data.get("chain_name", ""))
        idx = block_data["index"]

        # Ensure parent chain record exists to satisfy Foreign Key constraints
        if chain_name:
            cursor.execute(
                "INSERT OR IGNORE INTO chains (name, chain_type, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (chain_name, "sub", time.time(), time.time()),
            )

        # Remove existing block at same position (cascade deletes events via FK)
        cursor.execute(
            "DELETE FROM events WHERE block_hash IN "
            "(SELECT hash FROM blocks WHERE chain_name = ? AND \"index\" = ?)",
            (chain_name, idx),
        )
        cursor.execute(
            "DELETE FROM blocks WHERE chain_name = ? AND \"index\" = ?",
            (chain_name, idx),
        )

        events = block_data.get("events", [])
        metadata = block_data.get("metadata", {})
        if block_data.get("merkle_root") and "merkle_root" not in metadata:
            metadata["merkle_root"] = block_data["merkle_root"]

        cursor.execute(
            """
            INSERT INTO blocks
            (chain_name, "index", hash, previous_hash, timestamp, nonce, events_count, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chain_name,
                idx,
                block_data["hash"],
                block_data["previous_hash"],
                block_data["timestamp"],
                block_data.get("nonce", 0),
                len(events),
                orjson.dumps(metadata).decode("utf-8") if metadata else None,
            ),
        )

        block_hash = block_data["hash"]
        for event in events:
            cursor.execute(
                """
                INSERT INTO events
                (chain_name, block_hash, event_id, entity_id, event_type, timestamp, data, sender_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chain_name,
                    block_hash,
                    event.get("event_id"),
                    event.get("entity_id"),
                    event.get("event", "unknown"),
                    event.get("timestamp", 0.0),
                    orjson.dumps(event).decode("utf-8"),
                    event.get("submitted_by") or event.get("sender_id"),
                ),
            )

        conn.commit()
        return True

    def get_block_by_index(
        self, index: int, chain_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve a block by its integer index."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                return self._execute_get_block_by_index(cursor, index, chain_name)
        except Exception:
            self.logger.error(
                "Database operation failed",
                operation="get_block_by_index",
                index=index,
                chain_name=chain_name,
            )
            return None

    def _execute_get_block_by_index(
        self, cursor: Any, index: int, chain_name: str | None,
    ) -> dict[str, Any] | None:
        """Default SQLite implementation."""
        if chain_name:
            cursor.execute(
                "SELECT * FROM blocks WHERE \"index\" = ? AND chain_name = ?",
                (index, chain_name),
            )
        else:
            cursor.execute("SELECT * FROM blocks WHERE \"index\" = ?", (index,))
        row = cursor.fetchone()
        if not row:
            return None
        events = self._execute_fetch_block_events(cursor, row["hash"])
        return self._create_block_data(row, events)

    def get_latest_block(
        self, chain_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve the block with the highest index."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                return self._execute_get_latest_block(cursor, chain_name)
        except Exception:
            self.logger.error(
                "Database operation failed",
                operation="get_latest_block",
                chain_name=chain_name,
            )
            return None

    def _execute_get_latest_block(
        self, cursor: Any, chain_name: str | None,
    ) -> dict[str, Any] | None:
        """Default SQLite implementation."""
        if chain_name:
            cursor.execute(
                "SELECT * FROM blocks WHERE chain_name = ? ORDER BY \"index\" DESC LIMIT 1",
                (chain_name,),
            )
        else:
            cursor.execute(
                "SELECT * FROM blocks ORDER BY \"index\" DESC LIMIT 1"
            )
        row = cursor.fetchone()
        if not row:
            return None
        events = self._execute_fetch_block_events(cursor, row["hash"])
        return self._create_block_data(row, events)

    def get_event_by_id(self, event_id: str) -> dict[str, Any] | None:
        """Retrieve an event by its unique ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                return self._execute_get_event_by_id(cursor, event_id)
        except Exception:
            self.logger.error(
                "Database operation failed",
                operation="get_event_by_id",
                event_id=event_id,
            )
            return None

    @staticmethod
    def _execute_get_event_by_id(cursor: Any, event_id: str) -> dict[str, Any] | None:
        """Default SQLite implementation."""
        cursor.execute(
            "SELECT * FROM events WHERE event_id = ? LIMIT 1", (event_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "event_id": row["event_id"],
            "status": "ordered",
            "block_hash": row["block_hash"],
            "timestamp": row["timestamp"],
            "data": orjson.loads(row["data"]) if row["data"] else {},
        }

    def update_state(self, key: str, value: Any, last_block_hash: str) -> None:
        """Upsert a key-value pair in the chain_state table."""
        def _op():
            with self._get_connection() as conn:
                self._execute_update_state(conn, key, value, last_block_hash)
        self._execute_with_error_handling(
            "update_state", _op, key=key
        )

    @staticmethod
    def _execute_update_state(
        conn: Any, key: str, value: Any, last_block_hash: str,
    ) -> None:
        """Default SQLite implementation."""
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chain_state (key, value, last_block_hash, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                last_block_hash=excluded.last_block_hash,
                updated_at=excluded.updated_at
            """,
            (
                key,
                orjson.dumps(value).decode("utf-8") if not isinstance(value, (str, bytes)) else value,
                last_block_hash,
                time.time(),
            ),
        )
        conn.commit()

    def delete_chain(self, chain_name: str) -> bool:
        """Delete all data for a given chain (used for testing/cleanup)."""
        def _op():
            with self._get_connection() as conn:
                return self._execute_delete_chain(conn, chain_name)
        result = self._execute_with_error_handling(
            "delete_chain", _op, chain_name=chain_name
        )
        return result if result is not None else False

    @staticmethod
    def _execute_delete_chain(conn: Any, chain_name: str) -> bool:
        """Default SQLite implementation."""
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE chain_name = ?", (chain_name,))
        cursor.execute("DELETE FROM blocks WHERE chain_name = ?", (chain_name,))
        cursor.execute("DELETE FROM chains WHERE name = ?", (chain_name,))
        conn.commit()
        return True

    # --- close ---

    def close(self) -> None:
        """Release any held resources. Default no-op for per-request connections."""
