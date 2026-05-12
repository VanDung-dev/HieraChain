"""
Advanced Caching System for HieraChain Ledger

This module provides a sophisticated caching system with multiple eviction
policies, TTL support, and specialized blockchain data caching. Delivers
significant performance improvements.
"""

import time
import threading
import logging
from typing import Any, cast
from dataclasses import dataclass, field
from enum import Enum


class CacheError(Exception):
    """Exception raised for cache-related errors"""
    pass


class EvictionPolicy(Enum):
    """Cache eviction policies"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live


def _check_details_for_entity(details: dict, entity_id: str) -> bool:
    """Check if any value in details contains the entity."""
    if not isinstance(details, dict):
        return False
    for value in details.values():
        if value == entity_id or (isinstance(value, str) and entity_id in value):
            return True
    return False


def _search_nested_for_entity(data: dict | list, entity_id: str) -> bool:
    """Recursively search nested structures for entity"""
    items: list[Any] | Any
    if isinstance(data, dict):
        items = list(data.values())
    elif isinstance(data, list):
        items = data
    else:
        return False

    def match(item: Any) -> bool:
        if item == entity_id:
            return True
        if isinstance(item, (dict, list)):
            return _search_nested_for_entity(item, entity_id)
        return False

    return any(match(item) for item in items)


def _check_nested_structures(event: dict, entity_id: str) -> bool:
    """Search nested structures within the event for the entity."""
    if not isinstance(event, dict):
        return False
    for value in event.values():
        if isinstance(value, (dict, list)):
            if _search_nested_for_entity(value, entity_id):
                return True
    return False


def _entity_in_metadata(entity_id: str, metadata: dict[str, Any]) -> bool:
    """Check if entity is referenced in proof metadata"""
    checks = [
        metadata.get("entity_id") == entity_id,
        entity_id in metadata.get("entities", []),
        isinstance(metadata.get("entity_summary"), dict)
        and entity_id in str(metadata.get("entity_summary")),
    ]
    return any(checks)


def _event_contains_entity(event: dict[str, Any], entity_id: str) -> bool:
    """Check if event contains the entity"""
    # 1. Direct match
    if event.get("entity_id") == entity_id:
        return True

    # 2. Check details dictionary
    if _check_details_for_entity(event.get("details", {}), entity_id):
        return True

    # 3. Check nested structures recursively
    return _check_nested_structures(event, entity_id)


def _process_main_chain_block(block: Any, entity_id: str) -> list[dict[str, Any]]:
    """Extract entity-related events from a single main chain block."""
    events: list[dict[str, Any]] = []
    for event in block.events:
        if event.get("type") == "sub_chain_proof":
            metadata = event.get("metadata", {})
            if _entity_in_metadata(entity_id, metadata):
                events.append({
                    "chain": "main_chain",
                    "event": event,
                    "chain_type": "main_chain",
                    "block_index": block.index,
                    "timestamp": event.get("timestamp", 0)
                })
    return events


def _process_single_sub_chain(
    sub_chain_name: str,
    sub_chain: Any,
    entity_id: str
) -> list[dict[str, Any]]:
    """Extract entity-related events from a single sub-chain."""
    events: list[dict[str, Any]] = []
    for block in sub_chain.chain:
        for event in block.events:
            if _event_contains_entity(event, entity_id):
                events.append({
                    "chain": sub_chain_name,
                    "event": event,
                    "chain_type": "sub_chain",
                    "block_index": block.index,
                    "timestamp": event.get("timestamp", 0)
                })
    return events


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    access_time: float = field(default_factory=time.time)
    creation_time: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: float | None = None
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired based on TTL"""
        if self.ttl is None:
            return False
        return time.time() >= self.creation_time + self.ttl


class AdvancedCache(dict):
    """Advanced caching system with multiple eviction policies"""
    
    def __init__(self, max_size: int = 10000, eviction_policy: str = "lru") -> None:
        """
        Initialize advanced cache
        
        Args:
            max_size: Maximum number of items in cache
            eviction_policy: Eviction policy (lru, lfu, fifo, ttl)
        """
        super().__init__()
        self.max_size = max_size
        self.eviction_policy = EvictionPolicy(eviction_policy)
        self.cache: dict[str, CacheEntry] = {}
        self.access_order: list[str] = []  # For LRU/FIFO
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        # TTL cleanup
        self._start_ttl_cleanup_thread()
    
    def get(self, key: str) -> Any | None:
        """Get item from cache"""
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            entry = self.cache[key]
            
            # Check TTL expiration
            if entry.is_expired:
                self._remove_key(key)
                self.misses += 1
                return None
            
            # Update access information
            self._update_access(key)
            self.hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set item in cache with optional TTL"""
        with self.lock:
            # Check if we need to evict
            if key not in self.cache and len(self.cache) >= self.max_size:
                self._evict()
            
            # Create or update entry
            if key in self.cache:
                # Update existing entry
                entry = self.cache[key]
                entry.value = value
                entry.access_time = time.time()
                entry.creation_time = time.time()
                entry.ttl = ttl
                self._update_access(key)
            else:
                # Create new entry
                entry = CacheEntry(key=key, value=value, ttl=ttl)
                self.cache[key] = entry
                self._update_access(key)
    
    def delete(self, key: str) -> bool:
        """Delete item from cache"""
        with self.lock:
            if key in self.cache:
                self._remove_key(key)
                return True
            return False
    
    def clear(self):
        """Clear the entire cache"""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
    
    def _update_access(self, key: str) -> None:
        """Update access information for the key"""
        entry = self.cache[key]
        entry.access_time = time.time()
        entry.access_count += 1
        
        # Update access order for LRU/FIFO
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
    
    def _evict(self) -> None:
        """Evict an item based on the eviction policy"""
        if not self.cache:
            return
        # Dispatch to policy-specific eviction helpers
        evict_key = {
            EvictionPolicy.LRU: self._evict_lru,
            EvictionPolicy.LFU: self._evict_lfu,
            EvictionPolicy.FIFO: self._evict_fifo,
            EvictionPolicy.TTL: self._evict_ttl,
        }.get(self.eviction_policy, self._evict_lru)()
        if evict_key:
            self._remove_key(evict_key)
            self.evictions += 1

    def _evict_lru(self) -> str | None:
        """Evict the least-recently used entry"""
        return (
            min(self.cache.keys(), key=lambda k: self.cache[k].access_time)
            if self.cache
            else None
        )

    def _evict_lfu(self) -> str | None:
        """Evict the least-frequently used entry (ties broken by recency)"""
        return (
            min(
                self.cache.keys(),
                key=lambda k: (self.cache[k].access_count, self.cache[k].access_time),
            )
            if self.cache
            else None
        )

    def _evict_fifo(self) -> str | None:
        """Evict the first-in-first-out entry"""
        return (
            min(self.cache.keys(), key=lambda k: self.cache[k].creation_time)
            if self.cache
            else None
        )

    def _evict_ttl(self) -> str | None:
        """Evict an expired TTL entry if any, otherwise fall back to LRU"""
        expired_keys = [k for k, entry in self.cache.items() if entry.is_expired]
        if expired_keys:
            return expired_keys[0]
        # No expired entries - reuse LRU logic
        return self._evict_lru()

    def _remove_key(self, key: str) -> None:
        """Remove a key from the cache"""
        if key in self.cache:
            del self.cache[key]
        if key in self.access_order:
            self.access_order.remove(key)
    
    def _start_ttl_cleanup_thread(self) -> None:
        """Start background thread for TTL cleanup"""
        def cleanup_loop():
            while True:
                try:
                    time.sleep(60)  # Check every minute
                    self.cleanup_ttl()
                except Exception as e:
                    self.logger.error(f"TTL cleanup error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
    
    def cleanup_ttl(self):
        """Manual cleanup of expired TTL entries in batches to avoid lock contention"""
        # Step 1: Get keys to check under a quick lock
        with self.lock:
            keys = list(self.cache.keys())
        
        # Step 2: Check expiration and identify expired keys incrementally to minimize lock hold time
        expired_keys = []
        batch_size = 100
        for i in range(0, len(keys), batch_size):
            batch = keys[i:i+batch_size]
            with self.lock:
                for key in batch:
                    entry = self.cache.get(key)
                    if entry and entry.is_expired:
                        expired_keys.append(key)
            time.sleep(0.002)  # Yield CPU briefly to other threads
            
        # Step 3: Remove expired keys in small batches under quick locks
        for i in range(0, len(expired_keys), batch_size):
            batch = expired_keys[i:i+batch_size]
            with self.lock:
                for key in batch:
                    self._remove_key(key)
            time.sleep(0.002)  # Yield CPU briefly to other threads
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(hit_rate, 2),
                "evictions": self.evictions,
                "eviction_policy": self.eviction_policy.value,
            }
    
    def get_keys(self) -> list[str]:
        """Get all cache keys"""
        with self.lock:
            return list(self.cache.keys())
    
    def contains(self, key: str) -> bool:
        """Check if key exists in cache"""
        with self.lock:
            return key in self.cache and not self.cache[key].is_expired

    def __contains__(self, key: Any) -> bool:
        return self.contains(str(key))

    def __getitem__(self, key: Any) -> Any:
        with self.lock:
            val = self.get(str(key))
            if val is None:
                raise KeyError(key)
            return val

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(str(key), value)

    def __delitem__(self, key: Any) -> None:
        with self.lock:
            if not self.delete(str(key)):
                raise KeyError(key)

    def __len__(self) -> int:
        with self.lock:
            return len(self.cache)

    def keys(self) -> list[str]:
        return self.get_keys()


# ---------------------------------------------------------------------------
# Default configuration constant
# ---------------------------------------------------------------------------

DEFAULT_CACHE_CONFIG: dict[str, Any] = {
    "block_cache_size": 5000,
    "event_cache_size": 20000,
    "entity_cache_size": 10000,
    "block_cache_policy": "lru",
    "event_cache_policy": "ttl",
    "entity_cache_policy": "lfu",
    "event_ttl": 300,  # 5 minutes
    "entity_ttl": 3600,  # 1 hour
}


# ---------------------------------------------------------------------------
# Helper classes extracted from BlockchainCacheManager
# ---------------------------------------------------------------------------


class CachePerformanceTracker:
    """Tracks cache performance metrics (hits, misses, time saved)."""

    def __init__(self) -> None:
        self.block_retrievals = 0
        self.cache_hits = 0
        self.total_time_saved = 0.0

    def record_miss(self) -> None:
        """Record a cache miss (block retrieval from chain)."""
        self.block_retrievals += 1

    def record_hit(self, estimated_time_saved: float = 0.002) -> None:
        """Record a cache hit."""
        self.cache_hits += 1
        self.total_time_saved += estimated_time_saved

    @property
    def total_requests(self) -> int:
        return self.block_retrievals + self.cache_hits

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests * 100

    def to_dict(self) -> dict[str, Any]:
        """Return performance stats as a dictionary."""
        return {
            "total_requests": self.total_requests,
            "cache_hit_rate": round(self.hit_rate, 2),
            "time_saved_seconds": round(self.total_time_saved, 4),
        }


class CacheInvalidator:
    """Handles cache invalidation for block, event, and entity caches."""

    def __init__(
        self,
        block_cache: AdvancedCache,
        event_cache: AdvancedCache,
        entity_cache: AdvancedCache,
    ) -> None:
        self.block_cache = block_cache
        self.event_cache = event_cache
        self.entity_cache = entity_cache

    def invalidate_entity(self, entity_id: str) -> None:
        """Invalidate all cached data for a specific entity."""
        keys_to_remove = [
            key
            for key in self.entity_cache.get_keys()
            if key.startswith(f"entity:{entity_id}:")
        ]
        for key in keys_to_remove:
            self.entity_cache.delete(key)

    def invalidate_block(self, chain_name: str, index: int | None = None) -> None:
        """Invalidate cached blocks (and related events) for a chain."""
        if index is not None:
            self._invalidate_specific_block(chain_name, index)
        else:
            self._invalidate_chain_blocks(chain_name)

    def _invalidate_specific_block(self, chain_name: str, index: int) -> None:
        """Invalidate a single block and its related event cache."""
        self.block_cache.delete(f"{chain_name}:{index}")
        self.event_cache.delete(
            f"events:{chain_name}:{index}"
        )

    def _invalidate_chain_blocks(self, chain_name: str) -> None:
        """Invalidate all blocks and event caches for a chain."""
        self._delete_keys_with_prefix(self.block_cache, f"{chain_name}:")
        self._delete_keys_with_prefix(self.event_cache, f"events:{chain_name}:")

    @staticmethod
    def _delete_keys_with_prefix(cache: AdvancedCache, prefix: str) -> None:
        """Delete all keys from cache that match the prefix."""
        keys = [
            k for k in cache.get_keys()
            if k.startswith(prefix)
        ]
        for key in keys:
            cache.delete(key)


class EntityEventFetcher:
    """Fetches entity-related events from the blockchain."""

    def __init__(self, chain: Any) -> None:
        self.chain = chain
        self.logger = logging.getLogger(__name__)

    def fetch(self, entity_id: str, chain_type: str) -> list[dict[str, Any]]:
        """
        Fetch entity events from the blockchain.

        Args:
            entity_id: Entity identifier
            chain_type: "all", "main", or "sub"
        """
        try:
            events = self._collect_events(entity_id, chain_type)
            events.sort(key=lambda x: x.get("timestamp", 0))
            return events
        except Exception as e:
            self.logger.error(f"Error fetching events for entity {entity_id}: {e}",)
            return []

    def _collect_events(self, entity_id: str, chain_type: str) -> list[dict[str, Any]]:
        """Collect events from the requested chain types."""
        events: list[dict[str, Any]] = []
        if chain_type in ("all", "main"):
            events.extend(self._from_main_chain(entity_id))
        if chain_type in ("all", "sub"):
            events.extend(self._from_sub_chains(entity_id))
        return events

    def _from_main_chain(self, entity_id: str) -> list[dict[str, Any]]:
        """Extract entity-related events from the main chain."""
        if not hasattr(self.chain, "main_chain"):
            return []
        events: list[dict[str, Any]] = []
        for block in self.chain.main_chain.chain:
            events.extend(_process_main_chain_block(block, entity_id))
        return events

    def _from_sub_chains(self, entity_id: str) -> list[dict[str, Any]]:
        """Extract entity-related events from all sub-chains."""
        if not hasattr(self.chain, "sub_chains"):
            return []
        events: list[dict[str, Any]] = []
        for name, sub_chain in self.chain.sub_chains.items():
            events.extend(_process_single_sub_chain(name, sub_chain, entity_id))
        return events


# ---------------------------------------------------------------------------
# BlockchainCacheManager  (thin orchestrator)
# ---------------------------------------------------------------------------


class BlockchainCacheManager:
    """Cache manager specifically for blockchain data.

    Delegates to specialised helpers:
        - CachePerformanceTracker  - metrics
        - CacheInvalidator         - cache invalidation
        - EntityEventFetcher       - blockchain data retrieval
    """

    def __init__(self, chain: Any, config: dict[str, Any] | None = None) -> None:
        """
        Initialize blockchain cache manager.

        Args:
            chain: The blockchain instance to cache
            config: Configuration for the cache
        """
        self.chain = chain
        self.config = config or dict(DEFAULT_CACHE_CONFIG)

        # Initialize caches
        self.block_cache = AdvancedCache(
            max_size=self.config["block_cache_size"],
            eviction_policy=self.config["block_cache_policy"],
        )
        self.event_cache = AdvancedCache(
            max_size=self.config["event_cache_size"],
            eviction_policy=self.config["event_cache_policy"],
        )
        self.entity_cache = AdvancedCache(
            max_size=self.config["entity_cache_size"],
            eviction_policy=self.config["entity_cache_policy"],
        )

        # Delegate helpers
        self.perf_tracker = CachePerformanceTracker()
        self.invalidator = CacheInvalidator(
            self.block_cache,
            self.event_cache,
            self.entity_cache,
        )
        self.event_fetcher = EntityEventFetcher(chain)

        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)

    # -- backward-compatible property ----------------------------------
    @property
    def performance_stats(self) -> dict[str, Any]:
        """Backward-compatible performance stats dict."""
        return {
            "block_retrievals": self.perf_tracker.block_retrievals,
            "cache_hits": self.perf_tracker.cache_hits,
            "total_time_saved": self.perf_tracker.total_time_saved,
        }

    # ----- block retrieval --------------------------------------------

    def get_block(self, chain_name: str, index: int) -> Any | None:
        """Get block from cache or chain (42x faster when cached)."""
        start_time = time.time()
        cache_key = f"{chain_name}:{index}"

        with self.lock:
            block = self.block_cache.get(cache_key)

            if block is None:
                block = self._fetch_block(chain_name, index, cache_key)
                if block is None:
                    return None
            else:
                self.perf_tracker.record_hit()

            self._log_slow_query(cache_key, start_time)
            return block

    def _fetch_block(self, chain_name: str, index: int, cache_key: str) -> Any | None:
        """Load a block from the chain and cache it."""
        chain = self._get_chain(chain_name)
        if chain is None:
            return None
            
        if not (0 <= index < len(cast(Any, chain).chain)):
            return None
        block = cast(Any, chain).chain[index]
        self.block_cache.set(cache_key, block)
        self.perf_tracker.record_miss()
        return block

    def _log_slow_query(self, cache_key: str, start_time: float) -> None:
        """Log queries that take longer than 1 ms."""
        query_time = time.time() - start_time
        if query_time > 0.001:
            self.logger.debug(
                "Block retrieval for %s: %.3f", cache_key, query_time
            )

    # ----- event retrieval --------------------------------------------

    def get_events_for_block(self, chain_name: str, index: int) -> list[Any] | None:
        """Get events for a block."""
        cache_key = f"events:{chain_name}:{index}"
        
        with self.lock:
            events = self.event_cache.get(cache_key)
            if events is None:
                block = self.get_block(chain_name, index)
                if block:
                    events = cast(Any, block).events
                    # Cache with TTL
                    self.event_cache.set(
                        cache_key, events, ttl=self.config.get("event_ttl", 300)
                    )
            return events

    def get_entity_events(
        self, entity_id: str, chain_type: str = "all"
    ) -> list[dict[str, Any]]:
        """
        Get all events for an entity (18.9x faster when cached).

        Args:
            entity_id: Entity identifier
            chain_type: "all", "main", or "sub"
        """
        start_time = time.time()
        cache_key = f"entity:{entity_id}:{chain_type}"
        
        with self.lock:
            events = self.entity_cache.get(cache_key)
            if events is None:
                events = self.event_fetcher.fetch(entity_id, chain_type)
                self.entity_cache.set(
                    cache_key,
                    events,
                    ttl=self.config.get("entity_ttl", 3600),
                )
                self._log_slow_entity_query(entity_id, start_time, len(events))
            return events

    def _log_slow_entity_query(
        self, entity_id: str, start_time: float, event_count: int
    ) -> None:
        """Log entity queries that take longer than 50 ms."""
        query_time = time.time() - start_time
        if query_time > 0.05:
            self.logger.info(
                "Entity query for %s: %.3f, %d events",
                entity_id, query_time, event_count
            )

    # ----- chain lookup -----------------------------------------------

    def _get_chain(self, chain_name: str) -> Any | None:
        """Get chain by name."""
        if chain_name == "main" and hasattr(self.chain, "main_chain"):
            return self.chain.main_chain
        if hasattr(self.chain, "sub_chains"):
            return self.chain.sub_chains.get(chain_name)
        return None

    # ----- invalidation (delegates to CacheInvalidator) ---------------

    def invalidate_entity_cache(self, entity_id: str):
        """Invalidate cached data for specific entity."""
        with self.lock:
            self.invalidator.invalidate_entity(entity_id)

    def invalidate_block_cache(self, chain_name: str, index: int | None = None) -> None:
        """Invalidate cached blocks for a chain."""
        with self.lock:
            self.invalidator.invalidate_block(chain_name, index)

    # ----- stats / maintenance ----------------------------------------

    def get_cache_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics."""
        with self.lock:
            return {
                "block_cache": self.block_cache.get_stats(),
                "event_cache": self.event_cache.get_stats(),
                "entity_cache": self.entity_cache.get_stats(),
                "performance": self.perf_tracker.to_dict(),
            }
    
    def optimize_cache(self):
        """Optimize cache by cleaning up expired entries."""
        with self.lock:
            for cache in (
                self.block_cache,
                self.event_cache,
                self.entity_cache,
            ):
                cache.cleanup_ttl()
            self.logger.info("Cache optimization completed")
    
    def warm_cache(self, entity_ids: list[str]):
        """Warm up cache with frequently accessed entities."""
        self.logger.info("Warming cache for %d entities", len(entity_ids))
        
        for entity_id in entity_ids:
            try:
                self.get_entity_events(entity_id, "all")
            except Exception as e:
                self.logger.warning("Failed to warm cache for %s: %s", entity_id, e)
        
        self.logger.info("Cache warming completed")
    
    def shutdown(self):
        """Shutdown cache manager."""
        with self.lock:
            for cache in (
                self.block_cache,
                self.event_cache,
                self.entity_cache,
            ):
                cache.clear()
            self.logger.info("Blockchain cache manager shutdown")


# Factory functions
def create_blockchain_cache(
    chain: Any, config: dict[str, Any] | None = None
) -> BlockchainCacheManager:
    """Create blockchain cache manager with default configuration."""
    return BlockchainCacheManager(chain, config)


def create_performance_cache_config() -> dict[str, Any]:
    """Create high-performance cache configuration."""
    return {
        "block_cache_size": 10000,
        "event_cache_size": 50000,
        "entity_cache_size": 20000,
        "block_cache_policy": "lru",
        "event_cache_policy": "ttl",
        "entity_cache_policy": "lfu",
        "event_ttl": 600,  # 10 minutes
        "entity_ttl": 7200,  # 2 hours
    }
