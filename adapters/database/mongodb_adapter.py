"""
MongoDB adapter for Hierarchical Blockchain Framework

This module provides a MongoDB database adapter for the Hierarchical Blockchain Framework.
It implements storage and retrieval operations for blockchain data including chains, blocks, and events.
"""

import logging
from typing import List, Dict
from datetime import datetime

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

logger = logging.getLogger(__name__)

class MongoDBAdapter:
    """MongoDB database adapter for blockchain data storage"""
    
    def __init__(self, connection_string: str, database_name: str = "hierarchical_blockchain"):
        """
        Initialize MongoDB adapter
        
        Args:
            connection_string: MongoDB connection string
                Format: "mongodb://localhost:27017/" or MongoDB Atlas URI
            database_name: Name of the database to use
        """
        if not MONGO_AVAILABLE:
            raise ImportError("pymongo is required for MongoDB adapter. Install with: pip install pymongo")
        
        self.connection_string = connection_string
        self.database_name = database_name
        self.client = None
        self.db = None
        self._connect()
        self._create_indexes()
    
    def _connect(self):
        """Establish connection to MongoDB database"""
        try:
            self.client = MongoClient(self.connection_string)
            # Test the connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info("Connected to MongoDB database")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def _create_indexes(self):
        """Create necessary indexes for collections"""
        try:
            # Indexes for chains collection
            self.db.chains.create_index("name", unique=True)
            self.db.chains.create_index("type")
            
            # Indexes for blocks collection
            self.db.blocks.create_index([("chain_name", 1), ("block_index", 1)], unique=True)
            self.db.blocks.create_index("hash", unique=True)
            self.db.blocks.create_index("chain_name")
            
            # Indexes for events collection
            self.db.events.create_index("entity_id")
            self.db.events.create_index("chain_name")
            self.db.events.create_index("event_type")
            self.db.events.create_index("timestamp")
            self.db.events.create_index([("chain_name", 1), ("block_index", 1)])
            
            logger.info("MongoDB indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            raise
    
    def store_chain(self, chain_name: str, chain_type: str, parent_chain: str = None, metadata: Dict = None):
        """Store chain information"""
        try:
            chain_doc = {
                "name": chain_name,
                "type": chain_type,
                "parent_chain": parent_chain,
                "metadata": metadata or {},
                "created_at": datetime.utcnow()
            }
            
            self.db.chains.replace_one(
                {"name": chain_name},
                chain_doc,
                upsert=True
            )
            
            logger.debug(f"Stored chain: {chain_name}")
            
        except Exception as e:
            logger.error(f"Failed to store chain {chain_name}: {e}")
            raise
    
    def store_block(self, chain_name: str, block_data: Dict):
        """Store block data"""
        try:
            # Store block
            block_doc = {
                "chain_name": chain_name,
                "block_index": block_data['index'],
                "hash": block_data['hash'],
                "previous_hash": block_data['previous_hash'],
                "timestamp": datetime.fromtimestamp(block_data['timestamp']),
                "nonce": block_data.get('nonce', 0),
                "events": block_data['events'],
                "created_at": datetime.utcnow()
            }
            
            self.db.blocks.replace_one(
                {"chain_name": chain_name, "block_index": block_data['index']},
                block_doc,
                upsert=True
            )
            
            # Store individual events for faster querying
            for event in block_data['events']:
                event_doc = {
                    "chain_name": chain_name,
                    "block_index": block_data['index'],
                    "entity_id": event.get('entity_id'),
                    "event_type": event.get('event', event.get('event_type')),
                    "timestamp": datetime.fromtimestamp(event.get('timestamp', block_data['timestamp'])),
                    "details": event.get('details', {}),
                    "created_at": datetime.utcnow()
                }
                
                # Use upsert with a unique key composed of chain_name, block_index, and event content
                event_key = {
                    "chain_name": chain_name,
                    "block_index": block_data['index'],
                    "entity_id": event.get('entity_id'),
                    "event_type": event.get('event', event.get('event_type')),
                    "timestamp": datetime.fromtimestamp(event.get('timestamp', block_data['timestamp']))
                }
                
                self.db.events.replace_one(
                    event_key,
                    event_doc,
                    upsert=True
                )
            
            logger.debug(f"Stored block {block_data['index']} for chain {chain_name}")
            
        except Exception as e:
            logger.error(f"Failed to store block: {e}")
            raise
    
    def get_chain_blocks(self, chain_name: str, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get blocks for a specific chain"""
        try:
            query = {"chain_name": chain_name}
            
            cursor = self.db.blocks.find(query).sort("block_index", 1)
            
            if offset:
                cursor = cursor.skip(offset)
                
            if limit:
                cursor = cursor.limit(limit)
            
            blocks = []
            for doc in cursor:
                blocks.append({
                    'index': doc['block_index'],
                    'hash': doc['hash'],
                    'previous_hash': doc['previous_hash'],
                    'timestamp': doc['timestamp'].timestamp(),
                    'nonce': doc['nonce'],
                    'events': doc['events']
                })
            
            return blocks
            
        except Exception as e:
            logger.error(f"Failed to get blocks for chain {chain_name}: {e}")
            raise
    
    def get_entity_events(self, entity_id: str, chain_name: str = None) -> List[Dict]:
        """Get all events for a specific entity"""
        try:
            query = {"entity_id": entity_id}
            
            if chain_name:
                query["chain_name"] = chain_name
            
            cursor = self.db.events.find(query).sort("timestamp", 1)
            
            events = []
            for doc in cursor:
                events.append({
                    'chain_name': doc['chain_name'],
                    'block_index': doc['block_index'],
                    'event_type': doc['event_type'],
                    'timestamp': doc['timestamp'].timestamp(),
                    'details': doc['details']
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events for entity {entity_id}: {e}")
            raise
    
    def get_chain_stats(self, chain_name: str) -> Dict:
        """Get statistics for a specific chain"""
        try:
            # Get event statistics
            pipeline = [
                {"$match": {"chain_name": chain_name}},
                {
                    "$group": {
                        "_id": None,
                        "total_events": {"$sum": 1},
                        "unique_entities": {"$addToSet": "$entity_id"},
                        "first_event": {"$min": "$timestamp"},
                        "last_event": {"$max": "$timestamp"}
                    }
                },
                {
                    "$project": {
                        "total_events": 1,
                        "unique_entities": {"$size": "$unique_entities"},
                        "first_event": 1,
                        "last_event": 1
                    }
                }
            ]
            
            event_stats = list(self.db.events.aggregate(pipeline))
            
            # Get block count
            total_blocks = self.db.blocks.count_documents({"chain_name": chain_name})
            
            stats = {
                'chain_name': chain_name,
                'total_blocks': total_blocks,
                'total_events': 0,
                'unique_entities': 0,
                'first_event': None,
                'last_event': None
            }
            
            if event_stats:
                stats.update({
                    'total_events': event_stats[0].get('total_events', 0),
                    'unique_entities': event_stats[0].get('unique_entities', 0),
                    'first_event': event_stats[0]['first_event'].timestamp() if event_stats[0].get('first_event') else None,
                    'last_event': event_stats[0]['last_event'].timestamp() if event_stats[0].get('last_event') else None
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats for chain {chain_name}: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")