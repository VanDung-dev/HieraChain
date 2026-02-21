"""
Redis storage adapter for HieraChain Ledger

This module provides storage functionality for the HieraChain
using Redis as the backend. It supports storing chain metadata, blocks,
and provides indexing capabilities for entities and events.
"""

import json
import logging
import time
from typing import Any, Callable
import redis


logger = logging.getLogger(__name__)

def _parse_single_json_field(data: dict[str, Any], key: str):
    """Parse a single JSON field in data dictionary"""
    if key not in data:
        return
    try:
        data[key] = json.loads(data[key])
    except (json.JSONDecodeError, TypeError):
        if key == "events":
            data[key] = []


def _parse_json_fields(data: dict[str, Any], fields: list[str] | None = None):
    """Parse JSON fields in data dictionary"""
    for key in (fields or []):
        _parse_single_json_field(data, key)


def _convert_fields(
    data: dict[str, Any],
    fields: list[str] | None = None,
    converter: Callable = int
):
    """Convert fields in data dictionary using converter function"""
    for key in (fields or []):
        if key in data:
            try:
                data[key] = converter(data[key])
            except (ValueError, TypeError):
                pass


def _extract_event_from_block(
    block_data: dict[str, Any],
    entity_id: str,
    event_ref: dict[str, Any]
) -> dict[str, Any] | None:
    """Extract specific entity event from block data"""
    if not block_data:
        return None

    for event in block_data.get("events", []):
        if event.get("entity_id") == entity_id:
            return {
                "chain_name": event_ref["chain_name"],
                "block_index": event_ref["block_index"],
                "event_type": event.get("event", event.get("event_type")),
                "timestamp": event.get("timestamp"),
                "details": event.get("details", {})
            }
    return None


def _process_redis_data(
    data: dict[str, Any] | None,
    json_fields: list[str] | None = None,
    int_fields: list[str] | None = None,
    float_fields: list[str] | None = None
) -> dict[str, Any] | None:
    """Process data from Redis, converting fields to appropriate types"""
    if not data:
        return data

    _parse_json_fields(data, json_fields)
    _convert_fields(data, int_fields, int)
    _convert_fields(data, float_fields, float)

    return data


def _to_redis_mapping(data: dict[str, Any]) -> dict[str, str]:
    """Convert dictionary to Redis-compatible hash mapping."""
    return {
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in data.items()
    }


def _update_entity_indices(
    redis_client: redis.Redis,
    chain_name: str,
    block_data: dict[str, Any],
    entity_key_fn: Callable[[str], str]
) -> None:
    """Update entity events index in Redis."""
    for event in block_data.get("events", []):
        entity_id = event.get("entity_id")
        if not entity_id:
            continue

        entity_key = entity_key_fn(entity_id)
        event_ref = {
            "chain_name": chain_name,
            "block_index": block_data["index"],
            "event_type": event.get("event", event.get("event_type")),
            "timestamp": event.get("timestamp", block_data["timestamp"]),
            "block_hash": block_data["hash"]
        }
        timestamp = event.get("timestamp", block_data["timestamp"])
        redis_client.zadd(entity_key, {json.dumps(event_ref): timestamp})


def _update_chain_stats_counters(
    redis_client: redis.Redis,
    chain_name: str,
    block_data: dict[str, Any],
    stats_key_fn: Callable[[str], str]
) -> None:
    """Update chain statistics counters in Redis."""
    stats_key = stats_key_fn(chain_name)
    redis_client.hincrby(stats_key, "total_blocks", 1)

    events = block_data.get("events", [])
    redis_client.hincrby(stats_key, "total_events", len(events))

    for event in events:
        entity_id = event.get("entity_id")
        if entity_id:
            redis_client.sadd(f"{stats_key}:entities", entity_id)

    redis_client.hset(stats_key, "last_updated", str(time.time()))


def _fetch_blocks_batch(
    storage: "RedisStorageAdapter",
    chain_name: str,
    block_keys: list[str]
) -> list[dict]:
    """Fetch a batch of blocks from Redis."""
    blocks = []
    for block_key in block_keys:
        try:
            block_index = int(block_key.split(':')[-1])
            block_data = storage.get_block(chain_name, block_index)
            if block_data:
                blocks.append(block_data)
        except (ValueError, IndexError):
            continue
    return blocks


def _perform_redis_cleanup(
    redis_client: redis.Redis,
    chain_names: list[str],
    blocks_key_fn: Callable[[str], str],
    cutoff_time: float
) -> None:
    """Perform data cleanup in Redis."""
    for chain_name in chain_names:
        blocks_key = blocks_key_fn(chain_name)
        block_keys = redis_client.zrange(blocks_key, 0, -1)

        for block_key in block_keys:
            block_data = redis_client.hgetall(block_key)
            stored_at = float(block_data.get("stored_at", 0))

            if stored_at < cutoff_time:
                redis_client.delete(block_key)
                redis_client.zrem(blocks_key, block_key)
                logger.debug("Cleaned up old block: %s", block_key)


class RedisStorageAdapter:
    """Redis-based storage adapter for blockchain data"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        **kwargs
    ):
        """
        Initialize Redis storage adapter

        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (if required)
            **kwargs: Additional Redis connection parameters
        """
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

    def store_chain_metadata(
        self,
        chain_name: str,
        chain_type: str,
        parent_chain: str | None = None,
        metadata: dict | None = None
    ):
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
            self.redis_client.hset(chain_key, mapping=_to_redis_mapping(chain_data))
            self.redis_client.sadd("chains", chain_name)
            logger.debug("Stored chain metadata: %s", chain_name)

        except Exception as e:
            logger.error("Failed to store chain metadata %s: %s", chain_name, e)
            raise

    def store_block(self, chain_name: str, block_data: dict):
        """Store block data"""
        try:
            block_index = block_data["index"]
            block_key = self._get_block_key(chain_name, block_index)

            # Store block data
            full_data = {**block_data, "stored_at": time.time()}
            self.redis_client.hset(block_key, mapping=_to_redis_mapping(full_data))

            # Add to chain blocks list
            chain_blocks_key = self._get_chain_blocks_key(chain_name)
            self.redis_client.zadd(chain_blocks_key, {block_key: block_index})

            self._update_entity_index(chain_name, block_data)
            self._update_chain_stats(chain_name, block_data)
            logger.debug("Stored block %s for chain %s", block_index, chain_name)

        except Exception as e:
            logger.error("Failed to store block: %s", e)
            raise

    def _update_entity_index(self, chain_name: str, block_data: dict):
        """Update entity events index"""
        try:
            _update_entity_indices(
                self.redis_client,
                chain_name,
                block_data,
                self._get_entity_key
            )
        except Exception as e:
            logger.error("Failed to update entity index: %s", e)

    def _update_chain_stats(self, chain_name: str, block_data: dict):
        """Update chain statistics"""
        try:
            _update_chain_stats_counters(
                self.redis_client,
                chain_name,
                block_data,
                self._get_stats_key
            )
        except Exception as e:
            logger.error("Failed to update chain stats: %s", e)

    def get_chain_metadata(self, chain_name: str) -> dict | None:
        """Get chain metadata"""
        try:
            chain_key = self._get_chain_key(chain_name)
            chain_data = self.redis_client.hgetall(chain_key)

            if not chain_data:
                return None

            return _process_redis_data(
                chain_data, 
                json_fields=["metadata"], 
                float_fields=["created_at", "updated_at"]
            )

        except Exception as e:
            logger.error(f"Failed to get chain metadata {chain_name}: {e}")
            return None

    def get_block(self, chain_name: str, block_index: int) -> dict | None:
        """Get a specific block"""
        try:
            block_key = self._get_block_key(chain_name, block_index)
            block_data = self.redis_client.hgetall(block_key)

            if not block_data:
                return None

            # Process fields
            block_data = _process_redis_data(
                block_data,
                json_fields=["events"],
                int_fields=["index", "nonce"],
                float_fields=["timestamp", "stored_at"]
            )

            # Remove storage metadata
            block_data.pop("stored_at", None)

            return block_data

        except Exception as e:
            logger.error("Failed to get block %s for chain %s: %s", block_index, chain_name, e)
            return None

    def get_chain_blocks(
        self,
        chain_name: str,
        limit: int | None = None,
        offset: int = 0
    ) -> list[dict]:
        """Get blocks for a specific chain"""
        try:
            key = self._get_chain_blocks_key(chain_name)
            end = (offset + limit - 1) if limit else -1
            block_keys = self.redis_client.zrange(key, offset, end)
            return _fetch_blocks_batch(self, chain_name, block_keys)

        except Exception as e:
            logger.error("Failed to get blocks for chain %s: %s", chain_name, e)
            return []

    def _process_event_ref(self, event_ref_json: str, entity_id: str, chain_name: str = None) -> dict | None:
        """Process a single event reference JSON"""
        try:
            event_ref = json.loads(event_ref_json)

            # Filter by chain if specified
            if chain_name and event_ref.get("chain_name") != chain_name:
                return None

            # Get full event data from block
            block_data = self.get_block(event_ref["chain_name"], event_ref["block_index"])
            return _extract_event_from_block(block_data, entity_id, event_ref)

        except (json.JSONDecodeError, KeyError):
            return None

    def get_entity_events(
        self,
        entity_id: str,
        chain_name: str | None = None
    ) -> list[dict]:
        """Get all events for a specific entity"""
        try:
            entity_key = self._get_entity_key(entity_id)
            event_refs = self.redis_client.zrange(entity_key, 0, -1)

            events = []
            for ref_json in event_refs:
                event = self._process_event_ref(ref_json, entity_id, chain_name)
                if event:
                    events.append(event)
            return events

        except Exception as e:
            logger.error("Failed to get events for entity %s: %s", entity_id, e)
            return []

    def get_chain_stats(self, chain_name: str) -> dict:
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
            logger.error("Failed to get stats for chain %s: %s", chain_name, e)
            return {
                "chain_name": chain_name,
                "total_blocks": 0,
                "total_events": 0,
                "unique_entities": 0
            }

    def list_chains(self) -> list[str]:
        """list all stored chains"""
        try:
            return list(self.redis_client.smembers("chains"))
        except Exception as e:
            logger.error("Failed to list chains: %s", e)
            return []

    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data"""
        try:
            cutoff = time.time() - (days_to_keep * 24 * 60 * 60)
            _perform_redis_cleanup(
                self.redis_client,
                self.list_chains(),
                self._get_chain_blocks_key,
                cutoff
            )
            logger.info("Cleaned up data older than %s days", days_to_keep)
        except Exception as e:
            logger.error("Failed to cleanup old data: %s", e)

    def get_storage_info(self) -> dict:
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
            logger.error("Failed to get storage info: %s", e)
            return {}

    def flush_all(self):
        """Flush all data (use with caution!)"""
        try:
            self.redis_client.flushdb()
            logger.warning("Flushed all data from Redis database")
        except Exception as e:
            logger.error("Failed to flush data: %s", e)
            raise

    def close(self):
        """Close Redis connection"""
        try:
            self.redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error("Failed to close Redis connection: %s", e)
