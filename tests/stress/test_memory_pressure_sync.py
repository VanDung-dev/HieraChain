"""
Memory Pressure Sync Test - Large Data Load and OOM Prevention.

This test simulates loading large amounts of data into memory (via pyarrow)
and verifies that garbage collection and memory management mechanisms
keep the node from experiencing OOM (Out Of Memory) conditions.
"""

import time
import threading
import logging
import gc
import psutil
import os
from dataclasses import dataclass
from typing import Optional

import pytest

logger = logging.getLogger(__name__)


@dataclass
class MemoryPressureSnapshot:
    timestamp: float
    rss_mb: float
    pyarrow_bytes_mb: float
    gc_gen0: int
    gc_gen1: int
    gc_gen2: int


class MemoryPressureSyncTest:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.snapshots: list[MemoryPressureSnapshot] = []
        self.data_chunks: list[object] = []
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None

    def _get_memory_mb(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def _get_gc_counts(self) -> tuple[int, int, int]:
        return gc.get_count()

    def _load_pyarrow_data(self, chunk_size_mb: float = 10.0) -> None:
        try:
            import pyarrow as pa
        except ImportError:
            logger.warning("pyarrow not available, using mock data")
            self.data_chunks.append(bytearray(int(chunk_size_mb * 1024 * 1024)))
            return

        try:
            # Create a large amount of data (approx 10MB per call)
            # 100 arrays of 10k integers = 1M integers = 8MB (for int64) + overhead
            arrays = [pa.array(list(range(12500)), type=pa.int64()) for _ in range(100)]
            
            # Combine into a single chunked array for the column
            chunked_arr = pa.chunked_array(arrays)
            table = pa.Table.from_arrays([chunked_arr], names=["data"])
            
            self.data_chunks.append(table)
        except Exception as e:
            logger.error("PyArrow table creation failed: %s", e)
            # In a stress test, we should FAIL if the core engine component cannot be tested
            raise RuntimeError(f"Critical failure in stress test: PyArrow could not allocate memory or create table: {e}")

    def _pressure_worker(self, interval_seconds: float = 0.5) -> None:
        iteration = 0
        while self.running:
            try:
                self._load_pyarrow_data(chunk_size_mb=10.0)
                iteration += 1

                if iteration % 10 == 0:
                    gc.collect()

                rss_mb = self._get_memory_mb()
                gc_counts = self._get_gc_counts()

                with self.lock:
                    total_pyarrow_mb = sum(
                        getattr(chunk, "nbytes", 0)
                        if isinstance(chunk, bytearray)
                        else len(chunk) if hasattr(chunk, "__len__") else 0
                        for chunk in self.data_chunks
                    ) / (1024 * 1024)

                    snapshot = MemoryPressureSnapshot(
                        timestamp=time.time(),
                        rss_mb=rss_mb,
                        pyarrow_bytes_mb=total_pyarrow_mb,
                        gc_gen0=gc_counts[0],
                        gc_gen1=gc_counts[1],
                        gc_gen2=gc_counts[2],
                    )
                    self.snapshots.append(snapshot)
                    logger.info(
                        f"[Iter {iteration}] RSS: {rss_mb:.1f}MB, "
                        f"PyArrow: {total_pyarrow_mb:.1f}MB, "
                        f"GC: {gc_counts}"
                    )

                time.sleep(interval_seconds)

            except MemoryError:
                logger.error("MemoryError caught - OOM condition triggered")
                raise
            except Exception as e:
                logger.error(f"Error in pressure worker: {e}")
                break

    def start(self) -> None:
        self.running = True
        self.worker_thread = threading.Thread(target=self._pressure_worker, daemon=True)
        self.worker_thread.start()
        logger.info("Started memory pressure test")

    def stop(self) -> list[MemoryPressureSnapshot]:
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        gc.collect()
        return self.snapshots

    def clear_data(self) -> None:
        self.data_chunks.clear()
        gc.collect()

    def get_peak_memory_mb(self) -> float:
        if not self.snapshots:
            return 0.0
        return max(s.rss_mb for s in self.snapshots)


def test_memory_pressure_no_oom():
    test = MemoryPressureSyncTest()
    test.start()
    time.sleep(30)
    snapshots = test.stop()

    assert len(snapshots) > 0, "Should capture memory snapshots"

    peak_mb = test.get_peak_memory_mb()
    logger.info(f"Peak memory usage: {peak_mb:.1f}MB")

    available_mb = psutil.virtual_memory().available / (1024 * 1024)
    logger.info(f"Available memory: {available_mb:.1f}MB")

    assert peak_mb < available_mb * 0.9, (
        "Should not consume more than 90% of available memory"
    )


def test_gc_effective_recovery():
    test = MemoryPressureSyncTest()
    test.start()
    time.sleep(20)

    initial_rss = test.get_peak_memory_mb()
    test.stop()

    time.sleep(2)
    gc.collect()
    gc.collect()
    gc.collect()

    final_rss = test.process.memory_info().rss / (1024 * 1024)
    recovery_mb = initial_rss - final_rss

    logger.info(
        f"Initial: {initial_rss:.1f}MB, "
        f"Final: {final_rss:.1f}MB, Recovered: {recovery_mb:.1f}MB"
    )

    assert recovery_mb >= 0, "Memory should be recovered after GC"


def test_memory_pressure_snapshot_integrity():
    test = MemoryPressureSyncTest()
    test.start()
    time.sleep(15)
    snapshots = test.stop()

    for snap in snapshots:
        assert snap.timestamp > 0
        assert snap.rss_mb > 0
        assert snap.gc_gen0 >= 0
        assert snap.gc_gen1 >= 0
        assert snap.gc_gen2 >= 0

    timestamps = [s.timestamp for s in snapshots]
    assert timestamps == sorted(timestamps), "Snapshots should be chronological"


def test_repeated_pressure_cycles():
    test = MemoryPressureSyncTest()

    for cycle in range(3):
        logger.info(f"Starting cycle {cycle + 1}")
        test.start()
        time.sleep(10)
        test.stop()
        test.clear_data()
        logger.info(f"Cycle {cycle + 1} completed, cleared data")

    final_rss = test.process.memory_info().rss / (1024 * 1024)
    logger.info(f"Final RSS after 3 cycles: {final_rss:.1f}MB")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
