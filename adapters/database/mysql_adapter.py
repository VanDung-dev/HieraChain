"""
MySQL adapter for Hierarchical Blockchain Framework

This module provides a MySQL database adapter for the Hierarchical Blockchain Framework.
It implements storage and retrieval operations for blockchain data including chains, blocks, and events.
"""

import json
import logging
from typing import List, Dict
from datetime import datetime

try:
    import mysql.connector
    from mysql.connector import Error
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

logger = logging.getLogger(__name__)

class MySQLAdapter:
    """MySQL database adapter for blockchain data storage"""
    
    def __init__(self, host: str, database: str, user: str, password: str, port: int = 3306):
        """
        Initialize MySQL adapter
        
        Args:
            host: MySQL server host
            database: Database name
            user: Username for authentication
            password: Password for authentication
            port: Port number (default: 3306)
        """
        if not MYSQL_AVAILABLE:
            raise ImportError("mysql-connector-python is required for MySQL adapter. Install with: pip install mysql-connector-python")
        
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.connection = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Establish connection to MySQL database"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            
            if self.connection.is_connected():
                logger.info("Connected to MySQL database")
        except Error as e:
            logger.error(f"Failed to connect to MySQL: {e}")
            raise
    
    def _create_tables(self):
        """Create necessary tables for blockchain data"""
        cursor = self.connection.cursor()
        
        try:
            # Chains table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chains (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    parent_chain VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON
                )
            """)
            
            # Blocks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    chain_name VARCHAR(255) NOT NULL,
                    block_index INT NOT NULL,
                    hash VARCHAR(64) NOT NULL,
                    previous_hash VARCHAR(64),
                    timestamp TIMESTAMP NOT NULL,
                    nonce INT DEFAULT 0,
                    events JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_chain_block (chain_name, block_index),
                    FOREIGN KEY (chain_name) REFERENCES chains(name) ON DELETE CASCADE
                )
            """)
            
            # Events table (for faster querying)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    chain_name VARCHAR(255) NOT NULL,
                    block_index INT NOT NULL,
                    entity_id VARCHAR(255),
                    event_type VARCHAR(100) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    details JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chain_name) REFERENCES chains(name) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_chain_name ON blocks(chain_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_entity_id ON events(entity_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_chain_name ON events(chain_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
            
            self.connection.commit()
            logger.info("MySQL tables created successfully")
            
        except Error as e:
            logger.error(f"Failed to create tables: {e}")
            raise
        finally:
            cursor.close()
    
    def store_chain(self, chain_name: str, chain_type: str, parent_chain: str = None, metadata: Dict = None):
        """Store chain information"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO chains (name, type, parent_chain, metadata)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    type = VALUES(type),
                    parent_chain = VALUES(parent_chain),
                    metadata = VALUES(metadata)
            """, (chain_name, chain_type, parent_chain, json.dumps(metadata or {})))
            
            self.connection.commit()
            logger.debug(f"Stored chain: {chain_name}")
            
        except Error as e:
            logger.error(f"Failed to store chain {chain_name}: {e}")
            raise
        finally:
            cursor.close()
    
    def store_block(self, chain_name: str, block_data: Dict):
        """Store block data"""
        cursor = self.connection.cursor()
        
        try:
            # Store block
            cursor.execute("""
                INSERT INTO blocks (chain_name, block_index, hash, previous_hash, timestamp, nonce, events)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    hash = VALUES(hash),
                    previous_hash = VALUES(previous_hash),
                    timestamp = VALUES(timestamp),
                    nonce = VALUES(nonce),
                    events = VALUES(events)
            """, (
                chain_name,
                block_data['index'],
                block_data['hash'],
                block_data['previous_hash'],
                datetime.fromtimestamp(block_data['timestamp']),
                block_data.get('nonce', 0),
                json.dumps(block_data['events'])
            ))
            
            # Store individual events for faster querying
            for event in block_data['events']:
                cursor.execute("""
                    INSERT INTO events (chain_name, block_index, entity_id, event_type, timestamp, details)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    chain_name,
                    block_data['index'],
                    event.get('entity_id'),
                    event.get('event', event.get('event_type')),
                    datetime.fromtimestamp(event.get('timestamp', block_data['timestamp'])),
                    json.dumps(event.get('details', {}))
                ))
            
            self.connection.commit()
            logger.debug(f"Stored block {block_data['index']} for chain {chain_name}")
            
        except Error as e:
            logger.error(f"Failed to store block: {e}")
            raise
        finally:
            cursor.close()
    
    def get_chain_blocks(self, chain_name: str, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get blocks for a specific chain"""
        cursor = self.connection.cursor(dictionary=True)
        
        try:
            query = """
                SELECT block_index, hash, previous_hash, timestamp, nonce, events
                FROM blocks
                WHERE chain_name = %s
                ORDER BY block_index
            """
            params = [chain_name]
            
            if limit:
                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            blocks = []
            for row in rows:
                blocks.append({
                    'index': row['block_index'],
                    'hash': row['hash'],
                    'previous_hash': row['previous_hash'],
                    'timestamp': row['timestamp'].timestamp(),
                    'nonce': row['nonce'],
                    'events': json.loads(row['events']) if isinstance(row['events'], str) else row['events']
                })
            
            return blocks
            
        except Error as e:
            logger.error(f"Failed to get blocks for chain {chain_name}: {e}")
            raise
        finally:
            cursor.close()
    
    def get_entity_events(self, entity_id: str, chain_name: str = None) -> List[Dict]:
        """Get all events for a specific entity"""
        cursor = self.connection.cursor(dictionary=True)
        
        try:
            query = """
                SELECT chain_name, block_index, event_type, timestamp, details
                FROM events
                WHERE entity_id = %s
            """
            params = [entity_id]
            
            if chain_name:
                query += " AND chain_name = %s"
                params.append(chain_name)
            
            query += " ORDER BY timestamp"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            events = []
            for row in rows:
                events.append({
                    'chain_name': row['chain_name'],
                    'block_index': row['block_index'],
                    'event_type': row['event_type'],
                    'timestamp': row['timestamp'].timestamp(),
                    'details': json.loads(row['details']) if isinstance(row['details'], str) else row['details']
                })
            
            return events
            
        except Error as e:
            logger.error(f"Failed to get events for entity {entity_id}: {e}")
            raise
        finally:
            cursor.close()
    
    def get_chain_stats(self, chain_name: str) -> Dict:
        """Get statistics for a specific chain"""
        cursor = self.connection.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_blocks,
                    COUNT(DISTINCT entity_id) as unique_entities,
                    MIN(timestamp) as first_event,
                    MAX(timestamp) as last_event
                FROM events
                WHERE chain_name = %s
            """, (chain_name,))
            
            row = cursor.fetchone()
            
            # Get total events count
            cursor.execute("""
                SELECT COUNT(*) as total_events
                FROM events
                WHERE chain_name = %s
            """, (chain_name,))
            
            events_row = cursor.fetchone()
            
            return {
                'chain_name': chain_name,
                'total_blocks': row['total_blocks'],
                'unique_entities': row['unique_entities'],
                'total_events': events_row['total_events'],
                'first_event': row['first_event'].timestamp() if row['first_event'] else None,
                'last_event': row['last_event'].timestamp() if row['last_event'] else None
            }
            
        except Error as e:
            logger.error(f"Failed to get stats for chain {chain_name}: {e}")
            raise
        finally:
            cursor.close()
    
    def close(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("MySQL connection closed")