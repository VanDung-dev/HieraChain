"""
Test suite for Advanced Caching System

This module contains unit tests for the AdvancedCache class,
including cache operations, eviction policies, and TTL handling.
"""

import time

from hierarchical_blockchain.core.caching import AdvancedCache


def test_cache_basic_operations():
    """Test basic cache operations: set, get, and delete"""
    cache = AdvancedCache(max_size=100, eviction_policy="lru")
    
    # Test setting and getting items
    cache.set("key1", "value1")
    cache.set("key2", {"data": "value2"})
    
    assert cache.get("key1") == "value1"
    assert cache.get("key2") == {"data": "value2"}
    # Manually check if key exists
    assert "key1" in cache.cache
    assert "key3" not in cache.cache
    
    # Test cache size
    assert len(cache.cache) == 2
    
    # Test updating existing key
    cache.set("key1", "updated_value1")
    assert cache.get("key1") == "updated_value1"
    assert len(cache.cache) == 2  # Size should remain the same


def test_cache_eviction_lru():
    """Test LRU eviction policy"""
    cache = AdvancedCache(max_size=3, eviction_policy="lru")
    
    # Add items to fill cache
    cache.set("key1", "value1")
    time.sleep(0.01)  # Ensure different timestamps
    cache.set("key2", "value2")
    time.sleep(0.01)
    cache.set("key3", "value3")
    
    # Access key1 to make it recently used (should update access_time)
    time.sleep(0.01)
    cache.get("key1")
    
    # Add a new item - should evict key2 (least recently used)
    time.sleep(0.01)
    cache.set("key4", "value4")
    
    assert cache.get("key1") == "value1"  # Should still be in cache (recently accessed)
    assert cache.get("key2") is None      # Should be evicted (least recently used)
    assert cache.get("key3") == "value3"  # Should still be in cache
    assert cache.get("key4") == "value4"  # Should be in cache (newly added)
    assert len(cache.cache) == 3


def test_cache_eviction_fifo():
    """Test FIFO eviction policy"""
    cache = AdvancedCache(max_size=3, eviction_policy="fifo")
    
    # Add items to fill cache
    cache.set("key1", "value1")
    time.sleep(0.01)  # Ensure different timestamps
    cache.set("key2", "value2")
    time.sleep(0.01)
    cache.set("key3", "value3")
    
    # Add a new item - should evict key1 (first in)
    cache.set("key4", "value4")
    
    assert cache.get("key1") is None      # Should be evicted
    assert cache.get("key2") == "value2"  # Should still be in cache
    assert cache.get("key3") == "value3"  # Should still be in cache
    assert cache.get("key4") == "value4"  # Should be in cache
    assert len(cache.cache) == 3


def test_cache_ttl_expiration():
    """Test TTL expiration functionality"""
    cache = AdvancedCache(max_size=100, eviction_policy="ttl")
    
    # Add items with different TTLs
    cache.set("permanent_key", "permanent_value")  # No TTL
    cache.set("short_key", "short_value", ttl=0.1)  # 100ms TTL
    cache.set("long_key", "long_value", ttl=1.0)    # 1s TTL
    
    # All should be accessible immediately
    assert cache.get("permanent_key") == "permanent_value"
    assert cache.get("short_key") == "short_value"
    assert cache.get("long_key") == "long_value"
    
    # Wait for short TTL to expire
    time.sleep(0.15)  # 150ms
    
    # Check what's still available
    assert cache.get("permanent_key") == "permanent_value"  # Should still be there
    assert cache.get("short_key") is None                   # Should be expired
    assert cache.get("long_key") == "long_value"           # Should still be there
    
    # Wait for long TTL to expire
    time.sleep(0.9)  # Additional 900ms (total ~1.05s)
    
    assert cache.get("permanent_key") == "permanent_value"  # Should still be there
    assert cache.get("long_key") is None                    # Should be expired now