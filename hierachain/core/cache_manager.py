"""
Blockchain-aware cache manager for HieraChain Ledger.

Orchestrates AdvancedCache instances for blocks, events, and entities
with performance tracking, invalidation, and entity event fetching.
"""

import time
import threading
import logging
from typing import Any, cast

from hierachain.core.cache import AdvancedCache, DEFAULT_CACHE_CONFIG


def _check_details_for_entity(details: dict, entity_id: str) -> bool:
    if not isinstance(details, dict):
        return False
    for value in details.values():
        if value == entity_id or (isinstance(value, str) and entity_id in value):
            return True
    return False


def _search_nested_for_entity(data: dict | list, entity_id: str) -> bool:
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
    if not isinstance(event, dict):
        return False
    for value in event.values():
        if isinstance(value, (dict, list)):
            if _search_nested_for_entity(value, entity_id):
                return True
    return False


def _entity_in_metadata(entity_id: str, metadata: dict[str, Any]) -> bool:
    checks = [
        metadata.get("entity_id") == entity_id,
        entity_id in metadata.get("entities", []),
        isinstance(metadata.get("entity_summary"), dict)
        and entity_id in str(metadata.get("entity_summary")),
    ]
    return any(checks)


def _event_contains_entity(event: dict[str, Any], entity_id: str) -> bool:
    if event.get("entity_id") == entity_id:
        return True
    if _check_details_for_entity(event.get("details", {}), entity_id):
        return True
    return _check_nested_structures(event, entity_id)


def _process_main_chain_block(block: Any, entity_id: str) -> list[dict[str, Any]]:
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
    matching_events = (
        (block, event)
        for block in sub_chain.chain
        for event in block.events
        if _event_contains_entity(event, entity_id)
    )

    return [
        {
            "chain": sub_chain_name,
            "event": event,
            "chain_type": "sub_chain",
            "block_index": block.index,
            "timestamp": event.get("timestamp", 0)
        }
        for block, event in matching_events
    ]


class CachePerformanceTracker:
    def __init__(self) -> None:
        self.block_retrievals = 0
        self.cache_hits = 0
        self.total_time_saved = 0.0

    def record_miss(self) -> None:
        self.block_retrievals += 1

    def record_hit(self, estimated_time_saved: float = 0.002) -> None:
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
        return {
            "total_requests": self.total_requests,
            "cache_hit_rate": round(self.hit_rate, 2),
            "time_saved_seconds": round(self.total_time_saved, 4),
        }


class CacheInvalidator:
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
        keys_to_remove = [
            key
            for key in self.entity_cache.get_keys()
            if key.startswith(f"entity:{entity_id}:")
        ]
        for key in keys_to_remove:
            self.entity_cache.delete(key)

    def invalidate_block(self, chain_name: str, index: int | None = None) -> None:
        if index is not None:
            self._invalidate_specific_block(chain_name, index)
        else:
            self._invalidate_chain_blocks(chain_name)

    def _invalidate_specific_block(self, chain_name: str, index: int) -> None:
        self.block_cache.delete(f"{chain_name}:{index}")
        self.event_cache.delete(f"events:{chain_name}:{index}")

    def _invalidate_chain_blocks(self, chain_name: str) -> None:
        self._delete_keys_with_prefix(self.block_cache, f"{chain_name}:")
        self._delete_keys_with_prefix(self.event_cache, f"events:{chain_name}:")

    @staticmethod
    def _delete_keys_with_prefix(cache: AdvancedCache, prefix: str) -> None:
        keys = [
            k for k in cache.get_keys()
            if k.startswith(prefix)
        ]
        for key in keys:
            cache.delete(key)


class EntityEventFetcher:
    def __init__(self, chain: Any) -> None:
        self.chain = chain
        self.logger = logging.getLogger(__name__)

    def fetch(self, entity_id: str, chain_type: str) -> list[dict[str, Any]]:
        try:
            events = self._collect_events(entity_id, chain_type)
            events.sort(key=lambda x: x.get("timestamp", 0))
            return events
        except Exception as e:
            self.logger.error(f"Error fetching events for entity {entity_id}: {e}")
            return []

    def _collect_events(self, entity_id: str, chain_type: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if chain_type in ("all", "main"):
            events.extend(self._from_main_chain(entity_id))
        if chain_type in ("all", "sub"):
            events.extend(self._from_sub_chains(entity_id))
        return events

    def _from_main_chain(self, entity_id: str) -> list[dict[str, Any]]:
        if not hasattr(self.chain, "main_chain"):
            return []
        events: list[dict[str, Any]] = []
        for block in self.chain.main_chain.chain:
            events.extend(_process_main_chain_block(block, entity_id))
        return events

    def _from_sub_chains(self, entity_id: str) -> list[dict[str, Any]]:
        if not hasattr(self.chain, "sub_chains"):
            return []
        events: list[dict[str, Any]] = []
        for name, sub_chain in self.chain.sub_chains.items():
            events.extend(_process_single_sub_chain(name, sub_chain, entity_id))
        return events


class BlockchainCacheManager:
    def __init__(self, chain: Any, config: dict[str, Any] | None = None) -> None:
        self.chain = chain
        self.config = config or dict(DEFAULT_CACHE_CONFIG)
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
        self.perf_tracker = CachePerformanceTracker()
        self.invalidator = CacheInvalidator(
            self.block_cache,
            self.event_cache,
            self.entity_cache,
        )
        self.event_fetcher = EntityEventFetcher(chain)
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)

    def get_block(self, chain_name: str, index: int) -> Any | None:
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
        query_time = time.time() - start_time
        if query_time > 0.001:
            self.logger.debug(
                "Block retrieval for %s: %.3f", cache_key, query_time
            )

    def get_entity_events(
        self, entity_id: str, chain_type: str = "all"
    ) -> list[dict[str, Any]]:
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
        query_time = time.time() - start_time
        if query_time > 0.05:
            self.logger.info(
                "Entity query for %s: %.3f, %d events",
                entity_id, query_time, event_count
            )

    def _get_chain(self, chain_name: str) -> Any | None:
        if chain_name == "main" and hasattr(self.chain, "main_chain"):
            return self.chain.main_chain
        if hasattr(self.chain, "sub_chains"):
            return self.chain.sub_chains.get(chain_name)
        return None

    def shutdown(self):
        with self.lock:
            for cache in (
                self.block_cache,
                self.event_cache,
                self.entity_cache,
            ):
                cache.clear()
            self.logger.info("Blockchain cache manager shutdown")
