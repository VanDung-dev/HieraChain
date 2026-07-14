"""
Storage Backend Benchmark.

Compares throughput of SQLite vs Redis adapter under concurrent load.

NOTE:
  - SQLite: already available in the node, test via API
  - Redis: MUST add Redis service to docker-compose.test.yml first

These tests run inside stress-tester, calling storage adapter directly
(not via API) to measure raw performance.
"""

import time
import logging
import os
import random
import threading
import pytest

logger = logging.getLogger(__name__)


class _MemoryAdapter:
    """In-memory adapter matching FileStorageAdapter / RedisStorageAdapter API."""

    def __init__(self):
        self._blocks: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    def store_block(self, chain_name: str, block: dict) -> None:
        with self._lock:
            self._blocks.setdefault(chain_name, []).append(block)

    def get_block(self, chain_name: str, index: int) -> dict | None:
        with self._lock:
            chain = self._blocks.get(chain_name, [])
            return chain[index] if 0 <= index < len(chain) else None


def _load_sqlite():
    from hierachain.adapters.storage.file_storage import FileStorageAdapter
    return FileStorageAdapter(storage_path="/tmp/stress_benchmark.db")


def _load_redis():
    from hierachain.adapters.storage.redis_storage import RedisStorageAdapter
    return RedisStorageAdapter(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
    )


def _load_memory():
    return _MemoryAdapter()


STORAGE_FACTORIES = {
    "sqlite": _load_sqlite,
    "redis": _load_redis,
    "memory": _load_memory,
}


def _require_storage_adapter(backend: str):
    """Import storage adapter, skip if not available."""
    factory = STORAGE_FACTORIES.get(backend)
    if not factory:
        pytest.skip(f"Unknown backend: {backend}")
    try:
        return factory()
    except Exception as e:
        pytest.skip(f"{backend} adapter not available: {e}")


def _generate_block(index: int) -> dict:
    """Generate simulated block data."""
    import hashlib
    from hierachain.core import Block
    events = [
        {
            "entity_id": f"entity_{random.randint(1, 100)}",
            "event": random.choice(["create", "update", "delete"]),
            "timestamp": time.time(),
        }
        for _ in range(random.randint(1, 10))
    ]
    prev_hash = hashlib.sha256(f"block_{index - 1}".encode()).hexdigest() if index > 0 else None
    block = Block(
        index=index,
        events=events,
        previous_hash=prev_hash,
    )
    return block.to_dict()


class TestStorageBackendSQLite:
    """SQLite storage adapter benchmark."""

    @pytest.fixture(scope="class")
    def adapter(self):
        return _require_storage_adapter("sqlite")

    def test_sqlite_write_throughput(self, adapter):
        """Measure SQLite adapter write throughput."""
        num_blocks = 1000
        start = time.time()

        for i in range(num_blocks):
            adapter.store_block(f"bench_chain", _generate_block(i))

        elapsed = time.time() - start
        ops = num_blocks / elapsed if elapsed else 0
        logger.info("SQLite write: %d blocks in %.2fs (%.0f ops/sec)",
                     num_blocks, elapsed, ops)

    def test_sqlite_read_throughput(self, adapter):
        """Measure SQLite adapter read throughput."""
        chain_name = f"bench_read_{int(time.time())}"
        num_blocks = 500

        for i in range(num_blocks):
            adapter.store_block(chain_name, _generate_block(i))

        start = time.time()
        for i in range(num_blocks):
            adapter.get_block(chain_name, i)
        elapsed = time.time() - start

        ops = num_blocks / elapsed if elapsed else 0
        logger.info("SQLite read: %d blocks in %.2fs (%.0f ops/sec)",
                     num_blocks, elapsed, ops)

    def _run_concurrent_workers(self, adapter, chain_name: str, num_ops: int = 200) -> None:
        lock = threading.Lock()

        def _writer(w_id: int):
            for i in range(num_ops):
                with lock:
                    adapter.store_block(chain_name, _generate_block(w_id * num_ops + i))

        def _reader():
            for _ in range(num_ops):
                with lock:
                    try: adapter.get_block(chain_name, 0)
                    except Exception: pass

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(4)]
        threads += [threading.Thread(target=_reader) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=30)

    def test_sqlite_concurrent_access(self, adapter):
        """Measure SQLite under concurrent read/write."""
        self._run_concurrent_workers(adapter, f"bench_concurrent_{int(time.time())}")
        logger.info("SQLite concurrent test completed")


class TestStorageBackendMemory:
    """Memory storage benchmark (baseline)."""

    @pytest.fixture(scope="class")
    def adapter(self):
        return _require_storage_adapter("memory")

    def test_memory_write_throughput(self, adapter):
        """Measure Memory storage write throughput."""
        num_ops = 5000
        start = time.time()
        for i in range(num_ops):
            adapter.store_block(f"mem_chain", _generate_block(i))
        elapsed = time.time() - start
        logger.info("Memory write: %d ops in %.2fs (%.0f ops/sec)",
                     num_ops, elapsed, num_ops / elapsed if elapsed else 0)

    def test_memory_read_throughput(self, adapter):
        """Measure Memory storage read throughput."""
        chain = f"mem_read_{int(time.time())}"
        for i in range(1000):
            adapter.store_block(chain, _generate_block(i))

        start = time.time()
        for i in range(1000):
            adapter.get_block(chain, i)
        elapsed = time.time() - start

        logger.info("Memory read: 1000 ops in %.2fs (%.0f ops/sec)",
                     elapsed, 1000 / elapsed if elapsed else 0)


class TestStorageBackendRedis:
    """Redis storage adapter benchmark.

    Requires: Redis service added to docker-compose.test.yml
    and stress-tester can connect to `redis:6379`.
    """

    @pytest.fixture(scope="class")
    def adapter(self):
        return _require_storage_adapter("redis")

    def test_redis_write_throughput(self, adapter):
        """Measure Redis adapter write throughput."""
        num_ops = 1000
        start = time.time()

        for i in range(num_ops):
            adapter.store_block(f"redis_bench_chain", _generate_block(i))

        elapsed = time.time() - start
        logger.info("Redis write: %d ops in %.2fs (%.0f ops/sec)",
                     num_ops, elapsed, num_ops / elapsed if elapsed else 0)

    def test_redis_read_throughput(self, adapter):
        """Measure Redis adapter read throughput."""
        chain = f"redis_read_{int(time.time())}"
        for i in range(500):
            adapter.store_block(chain, _generate_block(i))

        start = time.time()
        for i in range(500):
            adapter.get_block(chain, i)
        elapsed = time.time() - start

        logger.info("Redis read: 500 ops in %.2fs (%.0f ops/sec)",
                     elapsed, 500 / elapsed if elapsed else 0)

    def test_redis_entity_index(self, adapter):
        """Measure entity index query performance in Redis."""
        import hashlib
        entity_id = f"bench_entity_{int(time.time())}"

        # Store events via blocks (Redis adapter indexes events from block data)
        for i in range(100):
            block = {
                "index": i,
                "hash": hashlib.sha256(f"block_{i}".encode()).hexdigest(),
                "timestamp": time.time() + i,
                "previous_hash": hashlib.sha256(f"block_{i - 1}".encode()).hexdigest() if i > 0 else "",
                "events_count": 1,
                "events": [{
                    "entity_id": entity_id,
                    "event": "benchmark",
                    "timestamp": time.time() + i,
                    "details": {"seq": i},
                }],
            }
            adapter.store_block("redis_bench_chain", block)

        # Query entity events
        start = time.time()
        events = adapter.get_entity_events(entity_id)
        elapsed = time.time() - start

        logger.info("Redis entity query: %d events in %.4fs",
                     len(events) if events else 0, elapsed)
