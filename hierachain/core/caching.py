"""
Caching system for HieraChain Ledger.

Re-exports from cache.py (AdvancedCache) and cache_manager.py
(BlockchainCacheManager, factory functions, helpers).
"""

from hierachain.core.cache import CacheError, EvictionPolicy, CacheEntry, AdvancedCache, DEFAULT_CACHE_CONFIG
from hierachain.core.cache_manager import (
    CachePerformanceTracker,
    CacheInvalidator,
    EntityEventFetcher,
    BlockchainCacheManager,
    create_blockchain_cache,
    create_performance_cache_config,
)

__all__ = [
    'CacheError',
    'EvictionPolicy',
    'CacheEntry',
    'AdvancedCache',
    'DEFAULT_CACHE_CONFIG',
    'CachePerformanceTracker',
    'CacheInvalidator',
    'EntityEventFetcher',
    'BlockchainCacheManager',
    'create_blockchain_cache',
    'create_performance_cache_config',
]
