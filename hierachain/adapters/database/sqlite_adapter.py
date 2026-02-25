"""
SQLite Database Adapter for HieraChain Ledger.

This module provides SQLite database integration for persistent storage
of blockchain data while maintaining Ledger guidelines and the
event-based model with hierarchical structure.
"""

import sqlite3
import json
import time
from typing import Any, Callable
from contextlib import contextmanager

from hierachain.core.block import Block, table_to_list_of_dicts
from hierachain.core.blockchain import Blockchain
from hierachain.security.secure_logging import get_storage_logger
from hierachain.config.settings import settings

logger = get_storage_logger()


def _extract_entity_id(event: Any) -> str | None:
    """Extract entity_id from event data if available."""
    if not hasattr(event, "data") or not isinstance(event.data, dict):
        return None

    entity_id = event.data.get("entity_id")
    if not entity_id and "product_id" in event.data:
        entity_id = event.data.get("product_id")
    return entity_id


def _insert_block_record(cursor: sqlite3.Cursor, chain_name: str, block: Block) -> None:
    """Insert or replace a block record in the database."""
    metadata_json = json.dumps(block.metadata) if hasattr(block, "metadata") else None

    cursor.execute("""
        INSERT OR REPLACE INTO blocks
        (chain_name, "index", hash, previous_hash, timestamp, nonce, events_count, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        chain_name,
        block.index,
        block.hash,
        block.previous_hash,
        block.timestamp,
        block.nonce,
        len(block.events),
        metadata_json,
        time.time()
    ))


def _insert_event_records(cursor: sqlite3.Cursor, chain_name: str, block_hash: str, events: list[Any]) -> None:
    """Insert events for a specific block into the database."""
    for event in events:
        entity_id = _extract_entity_id(event)
        event_data_json = json.dumps(event.data) if hasattr(event, "data") else "{}"

        cursor.execute("""
            INSERT OR IGNORE INTO events
            (chain_name, block_hash, event_id, entity_id, event_type, timestamp, data, sender_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chain_name,
            block_hash,
            getattr(event, "event_id", None),
            entity_id,
            event.event_type,
            event.timestamp,
            event_data_json,
            getattr(event, "sender_id", None)
        ))


def _store_block(cursor: sqlite3.Cursor, chain_name: str, block: Block) -> None:
    """Store a single block and its events."""
    _insert_block_record(cursor, chain_name, block)
    events_list = table_to_list_of_dicts(block.events)
    _insert_event_records(cursor, chain_name, block.hash, events_list)


def _create_event_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Create event dictionary from database row."""
    return {
        "chain_name": row["chain_name"],
        "entity_id": row["entity_id"],
        "event_type": row["event_type"],
        "timestamp": row["timestamp"],
        "data": json.loads(row["data"] or "{}")
    }


class SQLiteAdapter:
    """
    SQLite database adapter for the HieraChain Ledger.
    
    This adapter provides persistent storage capabilities:
    - Store and retrieve blockchain data
    - Maintain event-based model integrity
    - Support hierarchical chain relationships
    - Provide efficient querying by entity_id (as metadata)
    - Ensure Ledger compliance in data storage
    """
    
    def __init__(self, database_path: str = "hierachain.db"):
        """
        Initialize the SQLite adapter.
        
        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = database_path
        
        # Security check for Path Traversal (CWE-22)
        if ".." in self.database_path:
            raise ValueError(f"Security: Invalid database path '{self.database_path}'. Path traversal detected.")

        self.connection_pool_size = 5
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            self._create_tables(cursor)
            self._create_indexes(cursor)
            
            conn.commit()
    
    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        """Create all database tables."""
        self._create_chains_table(cursor)
        self._create_blocks_table(cursor)
        self._create_events_table(cursor)
        self._create_proofs_table(cursor)
    
    @staticmethod
    def _create_chains_table(cursor: sqlite3.Cursor) -> None:
        """Create chains table."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                chain_type TEXT NOT NULL,  -- 'main' or 'sub'
                domain_type TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
    
    @staticmethod
    def _create_blocks_table(cursor: sqlite3.Cursor) -> None:
        """Create blocks table."""
        cursor.execute("""
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
        """)

    @staticmethod
    def _create_events_table(cursor: sqlite3.Cursor) -> None:
        """Create events table."""
        cursor.execute("""
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
        """)

    @staticmethod
    def _create_proofs_table(cursor: sqlite3.Cursor) -> None:
        """Create proofs table."""
        cursor.execute("""
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
        """)
    
    @staticmethod
    def _create_indexes(cursor: sqlite3.Cursor) -> None:
        """Create database indexes for efficient querying."""
        indexes = [
            ("idx_events_entity_id", "events (entity_id)"),
            ("idx_events_type", "events (event_type)"),
            ("idx_events_timestamp", "events (timestamp)"),
            ("idx_events_chain", "events (chain_name)"),
            ("idx_blocks_hash_val", "blocks (hash)"),
            ("idx_blocks_chain", "blocks (chain_name)"),
            ("idx_proofs_sub_chain", "proofs (sub_chain_name)")
        ]
        
        for index_name, index_definition in indexes:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_definition}")
    
    @staticmethod
    def _execute_with_error_handling(operation: str, func: Callable, **context) -> Any:
        """
        Execute a database operation with standardized error handling.
        
        Args:
            operation: Name of the operation for logging
            func: Function to execute
            **context: Additional context for logging
            
        Returns:
            Result of the function or appropriate default value on error
        """
        try:
            return func()
        except Exception as e:
            logger.error("Database operation failed", operation=operation, **context)
            if settings.LOG_SQL_DETAIL:
                logger.debug("Database operation error detail", error_type=type(e).__name__)
            return None
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper error handling."""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def store_chain(self, chain: Blockchain) -> bool:
        """
        Store a blockchain in the database.
        
        Args:
            chain: Blockchain instance to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        def _store_chain_operation():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                chain_type = self._determine_chain_type(chain)
                domain_type = getattr(chain, 'domain_type', None)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO chains 
                    (name, chain_type, domain_type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (chain.name, chain_type, domain_type, time.time(), time.time()))
                
                conn.commit()
                return True
        
        result = self._execute_with_error_handling("store_chain", _store_chain_operation, chain_name=chain.name)
        return result if result is not None else False
    
    @staticmethod
    def _determine_chain_type(chain: Blockchain) -> str:
        """Determine if chain is main or sub chain."""
        return "main" if "MainChain" in str(type(chain)) else "sub"

    def load_chain(self, chain_name: str) -> dict[str, Any] | None:
        """
        Load a blockchain from the database.
        
        Args:
            chain_name: Name of the chain to load
            
        Returns:
            Chain data dictionary or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                chain_row = self._get_chain_info(cursor, chain_name)
                if not chain_row:
                    return None
                
                blocks = self._load_blocks_with_events(cursor, chain_name)
                
                return {
                    "name": chain_row['name'],
                    "chain_type": chain_row['chain_type'],
                    "domain_type": chain_row['domain_type'],
                    "chain": blocks,
                    "pending_events": []  # Not stored in DB
                }
                
        except Exception as e:
            logger.error("Database operation failed", operation="load_chain", chain_name=chain_name)
            if settings.LOG_SQL_DETAIL:
                logger.debug("Load chain error detail", error_type=type(e).__name__)
            return None
    
    @staticmethod
    def _get_chain_info(cursor: sqlite3.Cursor, chain_name: str) -> sqlite3.Row | None:
        """Get chain information from database."""
        cursor.execute("SELECT * FROM chains WHERE name = ?", (chain_name,))
        return cursor.fetchone()
    
    def _load_blocks_with_events(self, cursor: sqlite3.Cursor, chain_name: str) -> list[dict[str, Any]]:
        """Load all blocks with their events for a chain."""
        block_rows = self._get_block_rows(cursor, chain_name)
        
        blocks = []
        for block_row in block_rows:
            events = self._load_block_events(cursor, block_row['hash'])
            block_data = self._create_block_data(block_row, events)
            blocks.append(block_data)
        
        return blocks
    
    @staticmethod
    def _get_block_rows(cursor: sqlite3.Cursor, chain_name: str) -> list[sqlite3.Row]:
        """Get all block rows for a chain."""
        cursor.execute("""
            SELECT * FROM blocks WHERE chain_name = ? ORDER BY "index"
        """, (chain_name,))
        return cursor.fetchall()
    
    @staticmethod
    def _load_block_events(cursor: sqlite3.Cursor, block_hash: str) -> list[dict[str, Any]]:
        """Load events for a specific block."""
        cursor.execute("""
            SELECT entity_id, event_type, timestamp, data 
            FROM events WHERE block_hash = ? ORDER BY id
        """, (block_hash,))
        event_rows = cursor.fetchall()
        
        return [_create_event_from_row(row) for row in event_rows]

    @staticmethod
    def _create_block_data(block_row: sqlite3.Row, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Create block data dictionary from database row and events."""
        return {
            "index": block_row['index'],
            "events": events,  # Multiple events per block
            "timestamp": block_row['timestamp'],
            "previous_hash": block_row['previous_hash'],
            "nonce": block_row['nonce'],
            "hash": block_row['hash']
        }

    def _get_events_by_filter(self, filter_field: str, filter_value: str, chain_name: str | None, operation_name: str) -> list[dict[str, Any]]:
        """
        Get events by filtering on a specific field.
        
        Args:
            filter_field: Field name to filter on (e.g., 'entity_id', 'event_type')
            filter_value: Value to filter by
            chain_name: Optional chain name to filter by
            operation_name: Name of the operation for logging
            
        Returns:
            List of events matching the filter criteria
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                allowed_fields = {"chain_name", "event_type", "entity_id", "timestamp"}
                if filter_field not in allowed_fields:
                    logger.warning("Invalid filter field", filter_field=filter_field)
                    return []

                if chain_name:
                    cursor.execute(f"""
                        SELECT chain_name, block_index, entity_id, event_type, timestamp, details
                        FROM events WHERE {filter_field} = ? AND chain_name = ?
                        ORDER BY timestamp
                    """, (filter_value, chain_name))
                else:
                    cursor.execute(f"""
                        SELECT chain_name, block_index, entity_id, event_type, timestamp, details
                        FROM events WHERE {filter_field} = ?
                        ORDER BY timestamp
                    """, (filter_value,))
                
                rows = cursor.fetchall()
                return [_create_event_from_row(row) for row in rows]
                
        except Exception as e:
            logger.error("Database operation failed", operation=operation_name, **{filter_field: filter_value})
            if settings.LOG_SQL_DETAIL:
                logger.debug("Get events by filter error detail", error_type=type(e).__name__)
            return []
    
    def store_proof(
        self,
        main_chain_name: str,
        sub_chain_name: str,
        proof_hash: str,
        block_index: int,
        metadata: dict[str, Any]
    ) -> bool:
        """
        Store a proof submission from Sub-Chain to Main Chain.
        
        Args:
            main_chain_name: Name of the Main Chain
            sub_chain_name: Name of the Sub-Chain
            proof_hash: Hash of the block being proven
            block_index: Index of the block being proven
            metadata: Summary metadata (not detailed domain data)
            
        Returns:
            True if stored successfully, False otherwise
        """
        def _store_proof_operation():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO proofs 
                    (main_chain_name, sub_chain_name, proof_hash, block_index, metadata, submitted_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (main_chain_name, sub_chain_name, proof_hash, block_index,
                json.dumps(metadata), time.time(), time.time()))
                
                conn.commit()
                return True
        
        result = self._execute_with_error_handling("store_proof", _store_proof_operation)
        return result if result is not None else False
    
    def get_entity_events(self, entity_id: str, chain_name: str | None = None) -> list[dict[str, Any]]:
        """
        Get all events for a specific entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            chain_name: Optional chain name to filter by
            
        Returns:
            List of events for the entity
        """
        return self._get_events_by_filter("entity_id", entity_id, chain_name, "get_entity_events")
    
    def get_events_by_type(self, event_type: str, chain_name: str | None = None) -> list[dict[str, Any]]:
        """
        Get all events of a specific type.
        
        Args:
            event_type: Type of event to search for
            chain_name: Optional chain name to filter by
            
        Returns:
            List of events of the specified type
        """
        return self._get_events_by_filter("event_type", event_type, chain_name, "get_events_by_type")
    
    def get_chain_statistics(self, chain_name: str) -> dict[str, Any]:
        """
        Get statistics for a specific chain.
        
        Args:
            chain_name: Name of the chain
            
        Returns:
            Chain statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get basic chain info
                cursor.execute("SELECT * FROM chains WHERE name = ?", (chain_name,))
                chain_row = cursor.fetchone()
                
                if not chain_row:
                    return {}
                
                # Get block count
                cursor.execute("SELECT COUNT(*) as block_count FROM blocks WHERE chain_name = ?", (chain_name,))
                block_count = cursor.fetchone()['block_count']
                
                # Get event count
                cursor.execute("SELECT COUNT(*) as event_count FROM events WHERE chain_name = ?", (chain_name,))
                event_count = cursor.fetchone()['event_count']
                
                # Get unique entity count
                cursor.execute("""
                    SELECT COUNT(DISTINCT entity_id) as entity_count 
                    FROM events WHERE chain_name = ? AND entity_id IS NOT NULL
                """, (chain_name,))
                entity_count = cursor.fetchone()['entity_count']
                
                # Get event type distribution
                cursor.execute("""
                    SELECT event_type, COUNT(*) as count 
                    FROM events WHERE chain_name = ? 
                    GROUP BY event_type ORDER BY count DESC
                """, (chain_name,))
                event_types = {row['event_type']: row['count'] for row in cursor.fetchall()}
                
                return {
                    "chain_name": chain_name,
                    "chain_type": chain_row['chain_type'],
                    "domain_type": chain_row['domain_type'],
                    "total_blocks": block_count,
                    "total_events": event_count,
                    "unique_entities": entity_count,
                    "event_types": event_types,
                    "created_at": chain_row['created_at'],
                    "updated_at": chain_row['updated_at']
                }
                
        except Exception as e:
            logger.error("Database operation failed", operation="get_chain_statistics", chain_name=chain_name)
            if settings.LOG_SQL_DETAIL:
                logger.debug("Get chain statistics error detail", error_type=type(e).__name__)
            return {}
    
    def get_proof_history(self, sub_chain_name: str) -> list[dict[str, Any]]:
        """
        Get proof submission history for a Sub-Chain.
        
        Args:
            sub_chain_name: Name of the Sub-Chain
            
        Returns:
            List of proof submissions
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT main_chain_name, sub_chain_name, proof_hash, block_index, metadata, submitted_at
                    FROM proofs WHERE sub_chain_name = ?
                    ORDER BY submitted_at DESC
                """, (sub_chain_name,))
                
                rows = cursor.fetchall()
                
                proofs = []
                for row in rows:
                    proof = {
                        "main_chain_name": row['main_chain_name'],
                        "sub_chain_name": row['sub_chain_name'],
                        "proof_hash": row['proof_hash'],
                        "block_index": row['block_index'],
                        "metadata": json.loads(row['metadata'] or '{}'),
                        "submitted_at": row['submitted_at']
                    }
                    proofs.append(proof)
                
                return proofs
                
        except Exception as e:
            logger.error("Database operation failed", operation="get_proof_history", sub_chain_name=sub_chain_name)
            if settings.LOG_SQL_DETAIL:
                logger.debug("Get proof history error detail", error_type=type(e).__name__)
            return []
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        """
        Clean up old data from the database.
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Clean up old events
                cursor.execute("DELETE FROM events WHERE created_at < ?", (cutoff_time,))
                events_deleted = cursor.rowcount
                
                # Clean up old blocks (that no longer have events)
                cursor.execute("""
                    DELETE FROM blocks WHERE id NOT IN (
                        SELECT DISTINCT block_id FROM events
                    ) AND created_at < ?
                """, (cutoff_time,))
                blocks_deleted = cursor.rowcount
                
                # Clean up old proofs
                cursor.execute("DELETE FROM proofs WHERE created_at < ?", (cutoff_time,))
                proofs_deleted = cursor.rowcount
                
                conn.commit()

                logger.info("Cleanup completed",
                            events_deleted=events_deleted,
                            blocks_deleted=blocks_deleted,
                            proofs_deleted=proofs_deleted)
                return True

        except Exception as e:
            logger.error("Database operation failed", operation="cleanup")
            if settings.LOG_SQL_DETAIL:
                logger.debug("Cleanup error detail", error_type=type(e).__name__)
            return False
    
    def __str__(self) -> str:
        """String representation of the SQLite adapter."""
        return f"SQLiteAdapter(database_path={self.database_path})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the SQLite adapter."""
        return f"SQLiteAdapter(database_path={self.database_path})"