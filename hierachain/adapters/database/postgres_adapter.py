"""
PostgreSQL Database Adapter for HieraChain Ledger.

Provides PostgreSQL persistence for blockchain data by extending SQLBase.
Supports psycopg v3 ConnectionPool / psycopg2 / SQLAlchemy connection pooling with dictionary row access.
"""

from __future__ import annotations

import time
from typing import Any
from contextlib import contextmanager

import orjson
from hierachain.adapters.database.base.sql_adapter import SQLBase
from hierachain.security.secure_logging import get_storage_logger
from hierachain.core.blockchain import Blockchain
from hierachain.adapters.database.postgres_schema import init_database_schema

logger = get_storage_logger()


class PostgresAdapter(SQLBase):
    """
    PostgreSQL implementation of SQLBase adapter.
    Stores and retrieves blockchain data using high-performance connection pooling
    and native PostgreSQL dialects.
    """

    def __init__(self, database_url: str = "postgresql://hiera:hiera@localhost:5432/hierachain", pool_min: int = 1, pool_max: int = 10):
        self.database_url = database_url
        self.pool_min = pool_min
        self.pool_max = pool_max
        self._pool = None
        self._init_pool()
        self._init_schema()

    def _init_pool(self) -> None:
        """Initialize connection pool depending on available drivers."""
        try:
            import psycopg
            from psycopg_pool import ConnectionPool
            from psycopg.rows import dict_row

            self._pool = ConnectionPool(
                conninfo=self.database_url,
                min_size=self.pool_min,
                max_size=self.pool_max,
                kwargs={"row_factory": dict_row},
                open=True,
            )
            logger.info("Initialized psycopg3 connection pool for PostgreSQL")
        except ImportError:
            try:
                import psycopg2
                from psycopg2.pool import ThreadedConnectionPool
                from psycopg2.extras import RealDictCursor

                self._pool = ThreadedConnectionPool(
                    minconn=self.pool_min,
                    maxconn=self.pool_max,
                    dsn=self.database_url,
                    cursor_factory=RealDictCursor,
                )
                logger.info("Initialized psycopg2 connection pool for PostgreSQL")
            except ImportError:
                logger.warning(
                    "Neither psycopg (v3) nor psycopg2 installed. Connection will require driver installation."
                )

    @contextmanager
    def _get_connection(self):
        """Get a PostgreSQL connection with dict-like row access from the pool."""
        if self._pool is not None:
            # Handle psycopg v3 ConnectionPool
            if hasattr(self._pool, "connection"):
                with self._pool.connection() as conn:
                    yield conn
            # Handle psycopg2 ThreadedConnectionPool
            elif hasattr(self._pool, "getconn"):
                conn = self._pool.getconn()
                try:
                    yield conn
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    self._pool.putconn(conn)
        else:
            raise RuntimeError(
                "No PostgreSQL driver or pool available. Please install 'psycopg[binary]'."
            )

    def _init_schema(self) -> None:
        """Create PostgreSQL tables and composite indexes."""
        try:
            with self._get_connection() as conn:
                init_database_schema(conn.cursor())
                conn.commit()
        except Exception as e:
            logger.warning("PostgreSQL schema initialization deferred or failed: %s", e)

    def _execute_store_chain(self, conn: Any, chain: Blockchain) -> bool:
        """PostgreSQL dialect store chain with UPSERT."""
        cursor = conn.cursor()
        chain_type = self._determine_chain_type(chain)
        domain_type = getattr(chain, 'domain_type', None)
        cursor.execute(
            """
            INSERT INTO chains (name, chain_type, domain_type, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET chain_type = EXCLUDED.chain_type,
                domain_type = EXCLUDED.domain_type,
                updated_at = EXCLUDED.updated_at
            """,
            (chain.name, chain_type, domain_type, time.time(), time.time()),
        )
        conn.commit()
        return True

    @staticmethod
    def _execute_fetch_chain_info(cursor: Any, chain_name: str) -> Any | None:
        cursor.execute("SELECT * FROM chains WHERE name = %s", (chain_name,))
        return cursor.fetchone()

    @staticmethod
    def _execute_fetch_block_rows(cursor: Any, chain_name: str) -> list[Any]:
        cursor.execute(
            "SELECT * FROM blocks WHERE chain_name = %s ORDER BY \"index\" ASC",
            (chain_name,)
        )
        return cursor.fetchall()

    def _execute_fetch_block_events(self, cursor: Any, block_hash: str) -> list[dict[str, Any]]:
        cursor.execute(
            "SELECT * FROM events WHERE block_hash = %s ORDER BY id ASC",
            (block_hash,)
        )
        return [self._create_event_from_row(row) for row in cursor.fetchall()]

    def _execute_query_events_filter(
        self,
        cursor: Any,
        chain_name: str | None,
        entity_id: str | None,
        event_type: str | None,
        start_time: float | None,
        end_time: float | None,
        limit: int
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []

        if chain_name:
            query += " AND chain_name = %s"
            params.append(chain_name)
        if entity_id:
            query += " AND entity_id = %s"
            params.append(entity_id)
        if event_type:
            query += " AND event_type = %s"
            params.append(event_type)
        if start_time is not None:
            query += " AND timestamp >= %s"
            params.append(start_time)
        if end_time is not None:
            query += " AND timestamp <= %s"
            params.append(end_time)

        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, tuple(params))
        return [self._create_event_from_row(row) for row in cursor.fetchall()]

    def _execute_store_proof(
        self,
        conn: Any,
        main_chain_name: str,
        sub_chain_name: str,
        proof_hash: str,
        block_index: int,
        metadata: dict[str, Any] | None,
        submitted_at: float,
        created_at: float
    ) -> bool:
        cursor = conn.cursor()
        meta_json = orjson.dumps(metadata).decode() if metadata else None
        cursor.execute(
            """
            INSERT INTO proofs
            (main_chain_name, sub_chain_name, proof_hash, block_index, metadata, submitted_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                main_chain_name,
                sub_chain_name,
                proof_hash,
                block_index,
                meta_json,
                submitted_at,
                created_at,
            ),
        )
        conn.commit()
        return True

    @staticmethod
    def _execute_chain_statistics(cursor: Any, chain_name: str) -> dict[str, Any]:
        stats: dict[str, Any] = {"chain_name": chain_name}

        cursor.execute(
            "SELECT COUNT(*) as count FROM blocks WHERE chain_name = %s",
            (chain_name,)
        )
        stats["total_blocks"] = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(*) as count FROM events WHERE chain_name = %s",
            (chain_name,)
        )
        stats["total_events"] = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(DISTINCT entity_id) as count FROM events WHERE chain_name = %s",
            (chain_name,)
        )
        stats["unique_entities"] = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(*) as count FROM proofs WHERE sub_chain_name = %s",
            (chain_name,)
        )
        stats["submitted_proofs"] = cursor.fetchone()["count"]

        return stats

    def _execute_cleanup(self, cursor: Any, cutoff_time: float) -> None:
        cursor.execute(
            "DELETE FROM events WHERE created_at < %s",
            (cutoff_time,)
        )
        cursor.execute(
            "DELETE FROM proofs WHERE created_at < %s",
            (cutoff_time,)
        )

    def _execute_save_block(self, conn: Any, block_data: dict[str, Any]) -> bool:
        cursor = conn.cursor()
        meta_json = (
            orjson.dumps(block_data.get("metadata_json")).decode()
            if block_data.get("metadata_json")
            else None
        )
        cursor.execute(
            """
            INSERT INTO blocks
            (chain_name, "index", hash, previous_hash, timestamp, nonce, events_count, metadata_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (hash) DO NOTHING
            """,
            (
                block_data["chain_name"],
                block_data["index"],
                block_data["hash"],
                block_data["previous_hash"],
                block_data["timestamp"],
                block_data.get("nonce", 0),
                block_data.get("events_count", len(block_data.get("events", []))),
                meta_json,
                time.time(),
            ),
        )

        for event in block_data.get("events", []):
            data_json = (
                orjson.dumps(event.get("data", {})).decode()
                if isinstance(event.get("data"), (dict, list))
                else event.get("data")
            )
            cursor.execute(
                """
                INSERT INTO events
                (chain_name, block_hash, event_id, entity_id, event_type, timestamp, data, sender_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    block_data["chain_name"],
                    block_data["hash"],
                    event.get("event_id") or event.get("id"),
                    event.get("entity_id"),
                    event.get("event") or event.get("event_type", "unknown"),
                    event.get("timestamp", time.time()),
                    data_json,
                    event.get("sender_id"),
                    time.time(),
                ),
            )
        conn.commit()
        return True

    @staticmethod
    def _execute_get_block_by_index(cursor: Any, chain_name: str, index: int) -> Any | None:
        cursor.execute(
            "SELECT * FROM blocks WHERE chain_name = %s AND \"index\" = %s",
            (chain_name, index),
        )
        return cursor.fetchone()

    @staticmethod
    def _execute_get_latest_block(cursor: Any, chain_name: str) -> Any | None:
        cursor.execute(
            "SELECT * FROM blocks WHERE chain_name = %s ORDER BY \"index\" DESC LIMIT 1",
            (chain_name,),
        )
        return cursor.fetchone()

    @staticmethod
    def _execute_get_event_by_id(cursor: Any, event_id: str) -> dict[str, Any] | None:
        cursor.execute("SELECT * FROM events WHERE event_id = %s LIMIT 1", (event_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "chain_name": row["chain_name"],
            "entity_id": row["entity_id"],
            "event": row["event_type"],
            "timestamp": row["timestamp"],
            "data": orjson.loads(row["data"] or "{}"),
        }

    @staticmethod
    def _execute_update_state(conn: Any, key: str, value: str, last_block_hash: str | None) -> bool:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chain_state (key, value, last_block_hash, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                last_block_hash = EXCLUDED.last_block_hash,
                updated_at = EXCLUDED.updated_at
            """,
            (key, value, last_block_hash, time.time()),
        )
        conn.commit()
        return True

    @staticmethod
    def _execute_delete_chain(conn: Any, chain_name: str) -> bool:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chains WHERE name = %s", (chain_name,))
        conn.commit()
        return True

    def close(self) -> None:
        """Close connection pool on shutdown."""
        if self._pool is not None:
            if hasattr(self._pool, "close"):
                self._pool.close()
            self._pool = None

    def __str__(self) -> str:
        return f"PostgresAdapter(database_url={self.database_url})"

    def __repr__(self) -> str:
        return f"PostgresAdapter(database_url={self.database_url})"
