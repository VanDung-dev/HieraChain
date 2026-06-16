"""
Core caching primitives for HieraChain Ledger.

Provides AdvancedCache with multiple eviction policies (LRU, LFU, FIFO, TTL)
and the default cache configuration constant.
"""

import time
import threading
import logging
from typing import Any
from dataclasses import dataclass, field
from enum import Enum


class CacheError(Exception):
    pass


class EvictionPolicy(Enum):
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"


@dataclass
class CacheEntry:
    key: str
    value: Any
    access_time: float = field(default_factory=time.time)
    creation_time: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: float | None = None

    @property
    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() >= self.creation_time + self.ttl


class AdvancedCache(dict):
    def __init__(self, max_size: int = 10000, eviction_policy: str = "lru") -> None:
        super().__init__()
        self.max_size = max_size
        self.eviction_policy = EvictionPolicy(eviction_policy)
        self.cache: dict[str, CacheEntry] = {}
        self.access_order: list[str] = []
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self._start_ttl_cleanup_thread()

    def get(self, key: str) -> Any | None:
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            entry = self.cache[key]
            if entry.is_expired:
                self._remove_key(key)
                self.misses += 1
                return None
            self._update_access(key)
            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self.lock:
            if key not in self.cache and len(self.cache) >= self.max_size:
                self._evict()
            if key in self.cache:
                entry = self.cache[key]
                entry.value = value
                entry.access_time = time.time()
                entry.creation_time = time.time()
                entry.ttl = ttl
                self._update_access(key)
            else:
                entry = CacheEntry(key=key, value=value, ttl=ttl)
                self.cache[key] = entry
                self._update_access(key)

    def delete(self, key: str) -> bool:
        with self.lock:
            if key in self.cache:
                self._remove_key(key)
                return True
            return False

    def clear(self):
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0

    def _update_access(self, key: str) -> None:
        entry = self.cache[key]
        entry.access_time = time.time()
        entry.access_count += 1
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

    def _evict(self) -> None:
        if not self.cache:
            return
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
        return (
            min(self.cache.keys(), key=lambda k: self.cache[k].access_time)
            if self.cache
            else None
        )

    def _evict_lfu(self) -> str | None:
        return (
            min(
                self.cache.keys(),
                key=lambda k: (self.cache[k].access_count, self.cache[k].access_time),
            )
            if self.cache
            else None
        )

    def _evict_fifo(self) -> str | None:
        return (
            min(self.cache.keys(), key=lambda k: self.cache[k].creation_time)
            if self.cache
            else None
        )

    def _evict_ttl(self) -> str | None:
        expired_keys = [k for k, entry in self.cache.items() if entry.is_expired]
        if expired_keys:
            return expired_keys[0]
        return self._evict_lru()

    def _remove_key(self, key: str) -> None:
        if key in self.cache:
            del self.cache[key]
        if key in self.access_order:
            self.access_order.remove(key)

    def _start_ttl_cleanup_thread(self) -> None:
        def cleanup_loop():
            while True:
                try:
                    time.sleep(60)
                    self.cleanup_ttl()
                except Exception as e:
                    self.logger.error(f"TTL cleanup error: {e}")
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

    def cleanup_ttl(self):
        with self.lock:
            keys = list(self.cache.keys())
        expired_keys = []
        batch_size = 100
        for i in range(0, len(keys), batch_size):
            batch = keys[i:i+batch_size]
            with self.lock:
                for key in batch:
                    entry = self.cache.get(key)
                    if entry and entry.is_expired:
                        expired_keys.append(key)
            time.sleep(0.002)
        for i in range(0, len(expired_keys), batch_size):
            batch = expired_keys[i:i+batch_size]
            with self.lock:
                for key in batch:
                    self._remove_key(key)
            time.sleep(0.002)

    def get_stats(self) -> dict[str, Any]:
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
        with self.lock:
            return list(self.cache.keys())

    def contains(self, key: str) -> bool:
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


DEFAULT_CACHE_CONFIG: dict[str, Any] = {
    "block_cache_size": 5000,
    "event_cache_size": 20000,
    "entity_cache_size": 10000,
    "block_cache_policy": "lru",
    "event_cache_policy": "ttl",
    "entity_cache_policy": "lfu",
    "event_ttl": 300,
    "entity_ttl": 3600,
}
