"""
SQLite Database Adapter for Hierarchical-Blockchain Framework.

This module provides SQLite database integration for persistent storage
of blockchain data while maintaining framework guidelines and the
event-based model with hierarchical structure.
"""

import sqlite3
import json
import time
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

from core.block import Block
from core.blockchain import Blockchain


class SQLiteAdapter:
    """
    SQLite database adapter for the hierarchical blockchain framework.
    
    This adapter provides persistent storage capabilities:
    - Store and retrieve blockchain data
    - Maintain event-based model integrity
    - Support hierarchical chain relationships
    - Provide efficient querying by entity_id (as metadata)
    - Ensure framework compliance in data storage
    """
    
    def __init__(self, database_path: str = "hierarchical_blockchain.db"):
        """
        Initialize the SQLite adapter.
        
        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = database_path
        self.connection_pool_size = 5
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create chains table
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
            
            # Create blocks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain_name TEXT NOT NULL,
                    block_index INTEGER NOT NULL,
                    block_hash TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    nonce INTEGER DEFAULT 0,
                    events_count INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (chain_name) REFERENCES chains (name),
                    UNIQUE (chain_name, block_index),
                    UNIQUE (block_hash)
                )
            """)
            
            # Create events table - stores individual events from blocks
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain_name TEXT NOT NULL,
                    block_id INTEGER NOT NULL,
                    block_index INTEGER NOT NULL,
                    entity_id TEXT,  -- Metadata field, not identifier
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    details TEXT,  -- JSON string
                    created_at REAL NOT NULL,
                    FOREIGN KEY (chain_name) REFERENCES chains (name),
                    FOREIGN KEY (block_id) REFERENCES blocks (id)
                )
            """)
            
            # Create proofs table - for Main Chain proof submissions
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
            
            # Create indexes for efficient querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_entity_id ON events (entity_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_chain ON events (chain_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks (block_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_chain ON blocks (chain_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proofs_sub_chain ON proofs (sub_chain_name)")
            
            conn.commit()
    
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
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Determine chain type
                chain_type = "main" if "MainChain" in str(type(chain)) else "sub"
                domain_type = getattr(chain, 'domain_type', None)
                
                # Insert or update chain record
                cursor.execute("""
                    INSERT OR REPLACE INTO chains 
                    (name, chain_type, domain_type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (chain.name, chain_type, domain_type, time.time(), time.time()))
                
                # Store all blocks
                for block in chain.chain:
                    self._store_block(cursor, chain.name, block)
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error storing chain {chain.name}: {e}")
            return False
    
    @staticmethod
    def _store_block(cursor: sqlite3.Cursor, chain_name: str, block: Block) -> None:
        """Store a single block and its events."""
        # Insert block record
        cursor.execute("""
            INSERT OR REPLACE INTO blocks 
            (chain_name, block_index, block_hash, previous_hash, timestamp, nonce, events_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (chain_name, block.index, block.hash, block.previous_hash, 
              block.timestamp, block.nonce, len(block.events), time.time()))
        
        # Get block ID
        block_id = cursor.lastrowid
        
        # Store events
        for event in block.events:
            cursor.execute("""
                INSERT OR REPLACE INTO events 
                (chain_name, block_id, block_index, entity_id, event_type, timestamp, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (chain_name, block_id, block.index, 
                  event.get("entity_id"),  # Metadata field
                  event.get("event"), 
                  event.get("timestamp"), 
                  json.dumps(event.get("details", {})),
                  time.time()))
    
    @staticmethod
    def _create_event_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        """Create event dictionary from database row."""
        return {
            "chain_name": row['chain_name'],
            "block_index": row['block_index'],
            "entity_id": row['entity_id'],  # Metadata field
            "event": row['event_type'],
            "timestamp": row['timestamp'],
            "details": json.loads(row['details'] or '{}')
        }

    def load_chain(self, chain_name: str) -> Optional[Dict[str, Any]]:
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
                
                # Get chain info
                cursor.execute("SELECT * FROM chains WHERE name = ?", (chain_name,))
                chain_row = cursor.fetchone()
                
                if not chain_row:
                    return None
                
                # Get all blocks for this chain
                cursor.execute("""
                    SELECT * FROM blocks WHERE chain_name = ? ORDER BY block_index
                """, (chain_name,))
                block_rows = cursor.fetchall()
                
                # Load blocks with events
                blocks = []
                for block_row in block_rows:
                    # Get events for this block
                    cursor.execute("""
                        SELECT entity_id, event_type, timestamp, details 
                        FROM events WHERE block_id = ? ORDER BY id
                    """, (block_row['id'],))
                    event_rows = cursor.fetchall()
                    
                    # Reconstruct events
                    events = []
                    for event_row in event_rows:
                        events.append(self._create_event_from_row(event_row))
                    
                    # Create block data
                    block_data = {
                        "index": block_row['block_index'],
                        "events": events,  # Multiple events per block
                        "timestamp": block_row['timestamp'],
                        "previous_hash": block_row['previous_hash'],
                        "nonce": block_row['nonce'],
                        "hash": block_row['block_hash']
                    }
                    blocks.append(block_data)
                
                return {
                    "name": chain_row['name'],
                    "chain_type": chain_row['chain_type'],
                    "domain_type": chain_row['domain_type'],
                    "chain": blocks,
                    "pending_events": []  # Not stored in DB
                }
                
        except Exception as e:
            print(f"Error loading chain {chain_name}: {e}")
            return None
    
    def store_proof(self, main_chain_name: str, sub_chain_name: str, 
                   proof_hash: str, block_index: int, metadata: Dict[str, Any]) -> bool:
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
        try:
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
                
        except Exception as e:
            print(f"Error storing proof: {e}")
            return False
    
    def get_entity_events(self, entity_id: str, chain_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all events for a specific entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            chain_name: Optional chain name to filter by
            
        Returns:
            List of events for the entity
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if chain_name:
                    cursor.execute("""
                        SELECT chain_name, block_index, entity_id, event_type, timestamp, details
                        FROM events WHERE entity_id = ? AND chain_name = ?
                        ORDER BY timestamp
                    """, (entity_id, chain_name))
                else:
                    cursor.execute("""
                        SELECT chain_name, block_index, entity_id, event_type, timestamp, details
                        FROM events WHERE entity_id = ?
                        ORDER BY timestamp
                    """, (entity_id,))
                
                rows = cursor.fetchall()
                
                events = []
                for row in rows:
                    events.append(self._create_event_from_row(row))
                
                return events
                
        except Exception as e:
            print(f"Error getting entity events: {e}")
            return []
    
    def get_events_by_type(self, event_type: str, chain_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all events of a specific type.
        
        Args:
            event_type: Type of event to search for
            chain_name: Optional chain name to filter by
            
        Returns:
            List of events of the specified type
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if chain_name:
                    cursor.execute("""
                        SELECT chain_name, block_index, entity_id, event_type, timestamp, details
                        FROM events WHERE event_type = ? AND chain_name = ?
                        ORDER BY timestamp
                    """, (event_type, chain_name))
                else:
                    cursor.execute("""
                        SELECT chain_name, block_index, entity_id, event_type, timestamp, details
                        FROM events WHERE event_type = ?
                        ORDER BY timestamp
                    """, (event_type,))
                
                rows = cursor.fetchall()
                
                events = []
                for row in rows:
                    events.append(self._create_event_from_row(row))
                
                return events
                
        except Exception as e:
            print(f"Error getting events by type: {e}")
            return []
    
    def get_chain_statistics(self, chain_name: str) -> Dict[str, Any]:
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
            print(f"Error getting chain statistics: {e}")
            return {}
    
    def get_proof_history(self, sub_chain_name: str) -> List[Dict[str, Any]]:
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
                    SELECT main_chain_name, sub_chain_name, proof_hash, block_index, 
                           metadata, submitted_at
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
            print(f"Error getting proof history: {e}")
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
                
                print(f"Cleanup completed: {events_deleted} events, {blocks_deleted} blocks, {proofs_deleted} proofs deleted")
                return True
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
            return False
    
    def __str__(self) -> str:
        """String representation of the SQLite adapter."""
        return f"SQLiteAdapter(database_path={self.database_path})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the SQLite adapter."""
        return f"SQLiteAdapter(database_path={self.database_path})"