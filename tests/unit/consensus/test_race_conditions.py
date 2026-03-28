"""
Unit tests for race condition prevention.
"""

import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor


def test_concurrent_counter_increment():
    """Test that counter increments are thread-safe."""
    counter = {"value": 0}
    lock = threading.Lock()
    
    def increment():
        for _ in range(100):
            with lock:
                counter["value"] += 1
    
    threads = [threading.Thread(target=increment) for _ in range(10)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert counter["value"] == 1000


def test_concurrent_event_processing_no_loss():
    """Test that concurrent event processing doesn't lose events."""
    events = []
    lock = threading.Lock()
    
    def add_events(thread_id: int):
        for i in range(100):
            event = {
                "event": f"event_{thread_id}_{i}",
                "entity_id": f"entity_{thread_id}",
                "timestamp": time.time(),
                "details": {"index": i}
            }
            with lock:
                events.append(event)
    
    threads = [threading.Thread(target=add_events, args=(i,)) for i in range(10)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(events) == 1000


def test_concurrent_batch_creation():
    """Test concurrent batch creation."""
    batch_sizes = []
    lock = threading.Lock()
    
    def simulate_batch_creation(batch_id: int):
        events = [
            {"event": f"event_{batch_id}_{i}", "entity_id": "test", "timestamp": time.time(), "details": {}}
            for i in range(10)
        ]
        
        with lock:
            batch_sizes.append(len(events))
        
        return events
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(simulate_batch_creation, i) for i in range(100)]
        for f in futures:
            f.result()
    
    assert len(batch_sizes) == 100
    assert all(size == 10 for size in batch_sizes)


def test_lock_prevents_race_condition():
    """Test that using locks prevents race conditions."""
    class SafeCounter:
        def __init__(self):
            self.value = 0
            self._lock = threading.Lock()
        
        def increment_with_lock(self):
            with self._lock:
                current = self.value
                time.sleep(0.0001)
                self.value = current + 1
    
    safe = SafeCounter()
    threads = [threading.Thread(target=safe.increment_with_lock) for _ in range(100)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert safe.value == 100


def test_block_index_lock_protection():
    """Test that block index lock properly protects access."""
    from hierachain.core.block import Block
    from hierachain.consensus.ordering.block_manager import OrderingBlockManager
    
    class MockService:
        def __init__(self):
            self.blocks_created = 0
            self.status = "ACTIVE"
            
        class MockStorage:
            last_block = None
            
            def save_block(self, block, chain_name):
                return len(block.events), 0.1
        
        class MockConfig:
            def get(self, key):
                return "test_chain"
        
        class MockMetrics:
            def record_block_created(self, event_count, latency):
                pass
        
        class MockJournal:
            def log_event(self, event):
                pass
        
        class MockCommitQueue:
            def put(self, block):
                pass
        
        class MockBlockBuilder:
            pass
        
        storage_handler = MockStorage()
        config = MockConfig()
        metrics = MockMetrics()
        journal = MockJournal()
        commit_queue = MockCommitQueue()
        block_builder = MockBlockBuilder()
    
    service = MockService()
    manager = OrderingBlockManager(service)
    
    indices = []
    errors = []
    
    def get_and_increment():
        try:
            with manager._block_index_lock:
                idx = service.blocks_created
                time.sleep(0.001)
                service.blocks_created += 1
            indices.append(idx)
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=get_and_increment) for _ in range(50)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0
    assert len(indices) == len(set(indices))