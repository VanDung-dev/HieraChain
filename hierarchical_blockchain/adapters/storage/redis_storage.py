"""
Redis storage adapter for Hierarchical Blockchain Framework

This module provides storage functionality for the hierarchical blockchain
using Redis as the backend. It supports storing chain metadata, blocks,
and provides indexing capabilities for entities and events.
"""

import json
import logging
from typing import Dict, List, Optional
import time

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

class RedisStorageAdapter:
    """Redis-based storage adapter for blockchain data"""
    
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: str = None, **kwargs):
        """
        Initialize Redis storage adapter
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (if required)
            **kwargs: Additional Redis connection parameters
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis is required for Redis adapter. Install with: pip install redis")
        
        self.host = host
        self.port = port
        self.db = db
        
        # Connection parameters
        connection_params = {
            'host': host,
            'port': port,
            'db': db,
            'decode_responses': True,
            **kwargs
        }
        
        if password:
            connection_params['password'] = password
        
        try:
            self.redis_client = redis.Redis(**connection_params)
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        
        # Key prefixes for different data types
        self.CHAIN_PREFIX = "chain:"
        self.BLOCK_PREFIX = "block:"
        self.EVENT_PREFIX = "event:"
        self.ENTITY_PREFIX = "entity:"
        self.STATS_PREFIX = "stats:"
    
    def _get_chain_key(self, chain_name: str) -> str:
        """Get Redis key for chain metadata"""
        return f"{self.CHAIN_PREFIX}{chain_name}"
    
    def _get_block_key(self, chain_name: str, block_index: int) -> str:
        """Get Redis key for a specific block"""
        return f"{self.BLOCK_PREFIX}{chain_name}:{block_index}"
    
    def _get_entity_key(self, entity_id: str) -> str:
        """Get Redis key for entity events index"""
        return f"{self.ENTITY_PREFIX}{entity_id}"
    
    def _get_chain_blocks_key(self, chain_name: str) -> str:
        """Get Redis key for chain blocks list"""
        return f"{self.BLOCK_PREFIX}{chain_name}:list"
    
    def _get_stats_key(self, chain_name: str) -> str:
        """Get Redis key for chain statistics"""
        return f"{self.STATS_PREFIX}{chain_name}"
    
    def store_chain_metadata(self, chain_name: str, chain_type: str, parent_chain: str = None, metadata: Dict = None):
        """Store chain metadata"""
        try:
            chain_data = {
                "name": chain_name,
                "type": chain_type,
                "parent_chain": parent_chain,
                "metadata": metadata or {},
                "created_at": time.time(),
                "updated_at": time.time()
            }
            
            chain_key = self._get_chain_key(chain_name)
            self.redis_client.hset(chain_key, mapping={
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in chain_data.items()
            })
            
            # Add to chains list
            self.redis_client.sadd("chains", chain_name)
            
            logger.debug(f"Stored chain metadata: {chain_name}")
            
        except Exception as e:
            logger.error(f"Failed to store chain metadata {chain_name}: {e}")
            raise
    
    def store_block(self, chain_name: str, block_data: Dict):
        """Store block data"""
        try:
            block_index = block_data["index"]
            block_key = self._get_block_key(chain_name, block_index)
            
            # Store block data
            block_data_with_meta = block_data.copy()
            block_data_with_meta["stored_at"] = time.time()
            
            self.redis_client.hset(block_key, mapping={
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in block_data_with_meta.items()
            })
            
            # Add to chain blocks list (sorted set for ordering)
            chain_blocks_key = self._get_chain_blocks_key(chain_name)
            self.redis_client.zadd(chain_blocks_key, {block_key: block_index})
            
            # Update entity events index
            self._update_entity_index(chain_name, block_data)
            
            # Update chain statistics
            self._update_chain_stats(chain_name, block_data)
            
            logger.debug(f"Stored block {block_index} for chain {chain_name}")
            
        except Exception as e:
            logger.error(f"Failed to store block: {e}")
            raise
    
    def _update_entity_index(self, chain_name: str, block_data: Dict):
        """Update entity events index"""
        try:
            for event in block_data.get("events", []):
                entity_id = event.get("entity_id")
                if entity_id:
                    entity_key = self._get_entity_key(entity_id)
                    
                    event_ref = {
                        "chain_name": chain_name,
                        "block_index": block_data["index"],
                        "event_type": event.get("event", event.get("event_type")),
                        "timestamp": event.get("timestamp", block_data["timestamp"]),
                        "block_hash": block_data["hash"]
                    }
                    
                    # Use sorted set with timestamp as score for chronological ordering
                    timestamp = event.get("timestamp", block_data["timestamp"])
                    self.redis_client.zadd(entity_key, {json.dumps(event_ref): timestamp})
                    
        except Exception as e:
            logger.error(f"Failed to update entity index: {e}")
            # Don't raise - this is not critical for block storage
    
    def _update_chain_stats(self, chain_name: str, block_data: Dict):
        """Update chain statistics"""
        try:
            stats_key = self._get_stats_key(chain_name)
            
            # Increment block count
            self.redis_client.hincrby(stats_key, "total_blocks", 1)
            
            # Increment event count
            events_count = len(block_data.get("events", []))
            self.redis_client.hincrby(stats_key, "total_events", events_count)
            
            # Update unique entities count
            unique_entities = set()
            for event in block_data.get("events", []):
                entity_id = event.get("entity_id")
                if entity_id:
                    unique_entities.add(entity_id)
                    self.redis_client.sadd(f"{stats_key}:entities", entity_id)
            
            # Update timestamps
            self.redis_client.hset(stats_key, "last_updated", time.time())
            
        except Exception as e:
            logger.error(f"Failed to update chain stats: {e}")
            # Don't raise - this is not critical for block storage
    
    def get_chain_metadata(self, chain_name: str) -> Optional[Dict]:
        """Get chain metadata"""
        try:
            chain_key = self._get_chain_key(chain_name)
            chain_data = self.redis_client.hgetall(chain_key)
            
            if not chain_data:
                return None
            
            # Parse JSON fields
            for key in ["metadata"]:
                if key in chain_data:
                    try:
                        chain_data[key] = json.loads(chain_data[key])
                    except json.JSONDecodeError:
                        pass
            
            # Convert numeric fields
            for key in ["created_at", "updated_at"]:
                if key in chain_data:
                    try:
                        chain_data[key] = float(chain_data[key])
                    except ValueError:
                        pass
            
            return chain_data
            
        except Exception as e:
            logger.error(f"Failed to get chain metadata {chain_name}: {e}")
            return None
    
    def get_block(self, chain_name: str, block_index: int) -> Optional[Dict]:
        """Get a specific block"""
        try:
            block_key = self._get_block_key(chain_name, block_index)
            block_data = self.redis_client.hgetall(block_key)
            
            if not block_data:
                return None
            
            # Parse JSON fields
            for key in ["events"]:
                if key in block_data:
                    try:
                        block_data[key] = json.loads(block_data[key])
                    except json.JSONDecodeError:
                        block_data[key] = []
            
            # Convert numeric fields
            for key in ["index", "timestamp", "nonce", "stored_at"]:
                if key in block_data:
                    try:
                        if key == "index" or key == "nonce":
                            block_data[key] = int(block_data[key])
                        else:
                            block_data[key] = float(block_data[key])
                    except ValueError:
                        pass
            
            # Remove storage metadata
            block_data.pop("stored_at", None)
            
            return block_data
            
        except Exception as e:
            logger.error(f"Failed to get block {block_index} for chain {chain_name}: {e}")
            return None
    
    def get_chain_blocks(self, chain_name: str, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get blocks for a specific chain"""
        try:
            chain_blocks_key = self._get_chain_blocks_key(chain_name)
            
            # Get block keys in order
            if limit:
                block_keys = self.redis_client.zrange(chain_blocks_key, offset, offset + limit - 1)
            else:
                block_keys = self.redis_client.zrange(chain_blocks_key, offset, -1)
            
            blocks = []
            for block_key in block_keys:
                # Extract block index from key
                block_index = int(block_key.split(':')[-1])
                block_data = self.get_block(chain_name, block_index)
                if block_data:
                    blocks.append(block_data)
            
            return blocks
            
        except Exception as e:
            logger.error(f"Failed to get blocks for chain {chain_name}: {e}")
            return []
    
    def get_entity_events(self, entity_id: str, chain_name: str = None) -> List[Dict]:
        """Get all events for a specific entity"""
        try:
            entity_key = self._get_entity_key(entity_id)
            
            # Get all event references for this entity (ordered by timestamp)
            event_refs = self.redis_client.zrange(entity_key, 0, -1)
            
            events = []
            for event_ref_json in event_refs:
                try:
                    event_ref = json.loads(event_ref_json)
                    
                    # Filter by chain if specified
                    if chain_name and event_ref.get("chain_name") != chain_name:
                        continue
                    
                    # Get full event data from block
                    block_data = self.get_block(event_ref["chain_name"], event_ref["block_index"])
                    if block_data:
                        for event in block_data.get("events", []):
                            if event.get("entity_id") == entity_id:
                                events.append({
                                    "chain_name": event_ref["chain_name"],
                                    "block_index": event_ref["block_index"],
                                    "event_type": event.get("event", event.get("event_type")),
                                    "timestamp": event.get("timestamp"),
                                    "details": event.get("details", {})
                                })
                                break
                
                except json.JSONDecodeError:
                    continue
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events for entity {entity_id}: {e}")
            return []
    
    def get_chain_stats(self, chain_name: str) -> Dict:
        """Get statistics for a specific chain"""
        try:
            stats_key = self._get_stats_key(chain_name)
            stats_data = self.redis_client.hgetall(stats_key)
            
            if not stats_data:
                return {
                    "chain_name": chain_name,
                    "total_blocks": 0,
                    "total_events": 0,
                    "unique_entities": 0
                }
            
            # Get unique entities count
            unique_entities_count = self.redis_client.scard(f"{stats_key}:entities")
            
            return {
                "chain_name": chain_name,
                "total_blocks": int(stats_data.get("total_blocks", 0)),
                "total_events": int(stats_data.get("total_events", 0)),
                "unique_entities": unique_entities_count,
                "last_updated": float(stats_data.get("last_updated", 0))
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats for chain {chain_name}: {e}")
            return {
                "chain_name": chain_name,
                "total_blocks": 0,
                "total_events": 0,
                "unique_entities": 0
            }
    
    def list_chains(self) -> List[str]:
        """List all stored chains"""
        try:
            return list(self.redis_client.smembers("chains"))
        except Exception as e:
            logger.error(f"Failed to list chains: {e}")
            return []
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data"""
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            # Clean up old blocks
            for chain_name in self.list_chains():
                chain_blocks_key = self._get_chain_blocks_key(chain_name)
                block_keys = self.redis_client.zrange(chain_blocks_key, 0, -1)
                
                for block_key in block_keys:
                    block_data = self.redis_client.hgetall(block_key)
                    stored_at = float(block_data.get("stored_at", 0))
                    
                    if stored_at < cutoff_time:
                        # Remove block
                        self.redis_client.delete(block_key)
                        # Remove from chain blocks list
                        self.redis_client.zrem(chain_blocks_key, block_key)
                        logger.debug(f"Cleaned up old block: {block_key}")
            
            logger.info(f"Cleaned up data older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    def get_storage_info(self) -> Dict:
        """Get storage information"""
        try:
            info = self.redis_client.info()
            
            return {
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
                "chains_count": len(self.list_chains())
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            return {}
    
    def flush_all(self):
        """Flush all data (use with caution!)"""
        try:
            self.redis_client.flushdb()
            logger.warning("Flushed all data from Redis database")
        except Exception as e:
            logger.error(f"Failed to flush data: {e}")
            raise
    
    def close(self):
        """Close Redis connection"""
        try:
            self.redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Failed to close Redis connection: {e}")