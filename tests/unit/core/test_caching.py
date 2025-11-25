"""
Test suite for Advanced Caching System

This module contains unit tests for the AdvancedCache class,
including cache operations, eviction policies, and TTL handling.
"""

import time
import pytest
import threading
import random
import string

from hierachain.core.caching import AdvancedCache


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


def test_cache_multithreading_race_conditions():
    """Test cache behavior under multithreading race conditions"""
    cache = AdvancedCache(max_size=100, eviction_policy="lru")

    def worker(thread_id):
        for a in range(50):
            cache.set(f"key-{thread_id}-{a}", f"value-{thread_id}-{a}")
            # Random get operations
            if a % 5 == 0:
                cache.get(f"key-{thread_id}-{a - 1}")

    # Create multiple threads
    threads = []
    for i in range(5):  #5 threads
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Verify cache integrity
    assert len(cache.cache) <= 100 # Should not exceed max size

    # Verify that all keys are consistent
    total_keys = 0
    for i in range(5):
        for j in range(50):
            val = cache.get(f"key-{i}-{j}")
            if val is not None:
                assert val == f"value-{i}-{j}"
                total_keys += 1

    # At least some keys should exist
    assert total_keys > 0


def test_cache_large_memory_usage():
    """Test cache behavior with large memory usage"""
    cache = AdvancedCache(max_size=1000, eviction_policy="lru")

    # Add a lot of items to test memory usage
    large_data = {}
    for i in range(500):
        # Create large data items
        large_item = {f"field_{j}": f"value_{j}_{i}" for j in range(100)}
        cache.set(f"large_key_{i}", large_item)
        large_data[f"large_key_{i}"] = large_item

    # Verify cache size
    assert len(cache.cache) == 500

    # Verify data integrity for sampled items
    for i in [0, 100, 250, 499]:  # Sample checks
        key = f"large_key_{i}"
        cached_value = cache.get(key)
        assert cached_value is not None
        assert cached_value == large_data[key]


def test_cache_edge_cases_ttl():
    """Test edge cases for TTL functionality"""
    cache = AdvancedCache(max_size=100, eviction_policy="ttl")

    # Test with zero TTL (should expire immediately)
    cache.set("zero_ttl_key", "zero_ttl_value", ttl=0)
    # Give a small delay for expiration
    time.sleep(0.01)
    assert cache.get("zero_ttl_key") is None

    # Test with negative TTL (should behave as no TTL or expire immediately)
    cache.set("negative_ttl_key", "negative_ttl_value", ttl=-1)
    # Behavior depends on implementation - either stored permanently or expires immediately
    # We'll checkit doesn't crash and behaves consistently
    value = cache.get("negative_ttl_key")
    # Either None or the value is acceptable
    assert value is None or value == "negative_ttl_value"

    # Test with very large TTL
    cache.set("large_ttl_key", "large_ttl_value", ttl=1000000)  # ~11 days
    assert cache.get("large_ttl_key") == "large_ttl_value"


# Performance/load testing
def test_cache_performance_under_load(benchmark):
    """Test cache performance under high load"""
    def execute():
        cache = AdvancedCache(max_size=5000, eviction_policy="lru")

        # Generate test data
        test_data = {}
        for i in range(1000):
            key = f"test_key_{i}"
            value = {"data": f"test_value_{i}", "index": i, "timestamp": time.time()}
            test_data[key] = value

        # Measure insertion performance
        start_time = time.time()
        for key, value in test_data.items():
            cache.set(key, value)
        insert_time = time.time() - start_time

        # Verify all data was inserted
        assert len(cache.cache) == 1000

        # Measure retrieval performance
        start_time = time.time()
        for key in test_data.keys():
            value = cache.get(key)
            assert value is not None
            assert value["data"].startswith("test_value_")
        retrieve_time = time.time() - start_time

        # Performance checks (these times might vary based on system)
        assert insert_time < 1.0  # Should insert 1000 items in less than 1 second
        assert retrieve_time < 0.5  # Should retrieve 1000 items in less than 0.5 seconds

        return cache, test_data, insert_time, retrieve_time

    benchmark(execute)



# Property-based testing with Hypothesis
@pytest.mark.parametrize("policy", ["lru", "fifo", "ttl"])
def test_cache_eviction_policies_property(policy):
    """Property-based test for different cache eviction policies"""
    cache = AdvancedCache(max_size=5, eviction_policy=policy)

    # Add more items than cache can hold
    for i in range(10):
        cache.set(f"key_{i}", f"value_{i}")

    # Cache should never exceed max_size
    assert len(cache.cache) <= 5


# Fuzz testing
def test_cache_with_fuzzed_inputs():
    """Fuzz testing with randomized cache operations"""
    cache = AdvancedCache(max_size=100, eviction_policy="lru")

    # Perform random operations
    for _ in range(1000):
        operation = random.choice(["set", "get", "delete"])

        # Generate random key
        key = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(1, 50)))

        if operation == "set":
            # Generate random value
            value_type = random.choice(["string", "dict", "list", "int", "float"])
            if value_type == "string":
                value = ''.join(random.choices(string.printable, k=random.randint(0, 1000)))
            elif value_type == "dict":
                value = {f"key_{i}": random.random() for i in range(random.randint(0, 100))}
            elif value_type == "list":
                value = [random.random() for _ in range(random.randint(0, 100))]
            elif value_type == "int":
                value = random.randint(-1000000, 1000000)
            else:  # float
                value = random.uniform(-1000000.0, 1000000.0)

            # Random TTL
            ttl = random.choice([None, random.uniform(0, 10)])

            cache.set(key, value, ttl=ttl)
        elif operation == "get":
            # Just try to get the key
            cache.get(key)
        else:  # delete
            cache.delete(key)

    # Cache should still be functional
    assert len(cache.cache) <= 100
    # Stats should be consistent
    stats = cache.get_stats()
    assert stats["size"] == len(cache.cache)
    assert stats["max_size"] == 100


# Integration testing between cache and other modules
def test_cache_integration_with_multithreading():
    """Integration test for cache with multithreading operations"""
    cache = AdvancedCache(max_size=1000, eviction_policy="lru")

    def cache_worker(worker_id):
        for a in range(100):
            key = f"worker_{worker_id}_key_{a}"
            value = {"worker_id": worker_id, "iteration": a, "data": f"data_{a}"}
            cache.set(key, value)

            # Try to get some keys
            for j in range(5):
                get_key = f"worker_{random.randint(0, 9)}_key_{random.randint(0, 99)}"
                cache.get(get_key)

    # Create and start multiple worker threads
    threads = []
    for i in range(10):
        t = threading.Thread(target=cache_worker, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Verify cache state
    assert len(cache.cache) <= 1000
    assert cache.hits >= 0
    assert cache.misses >= 0
    assert cache.evictions >= 0
