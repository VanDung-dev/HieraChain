"""
Memory Leak Soak Test - Long Duration Memory Growth Monitoring.

This test monitors RSS (Resident Set Size) growth patterns during sustained
event processing to detect memory leaks in the HieraChain process.
"""

import gc
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import pytest

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    timestamp: float
    rss_mb: float
    vms_mb: float
    gc_gen0: int
    gc_gen1: int
    gc_gen2: int


@dataclass
class SoakTestConfig:
    test_duration_seconds: int = 300
    allocation_interval_seconds: float = 0.5
    allocation_size_kb: int = 512
    leak_threshold_mb_per_hour: float = 50.0
    max_memory_mb: float = 850.0
    sample_interval_seconds: float = 2.0


class MemoryLeakSoakTest:
    def __init__(self, config: Optional[SoakTestConfig] = None):
        self.config = config or SoakTestConfig()
        self.process = pytest.importorskip("psutil").Process(os.getpid())
        self.snapshots: list[MemorySnapshot] = []
        self.allocations: list[bytearray] = []
        self.running = False
        self.worker_count = 0

    def _get_memory_mb(self) -> tuple[float, float]:
        mem_info = self.process.memory_info()
        return mem_info.rss / (1024 * 1024), mem_info.vms / (1024 * 1024)

    def _get_gc_counts(self) -> tuple[int, int, int]:
        return gc.get_count()

    def _allocation_worker(self) -> None:
        allocated_mb = 0
        while self.running:
            try:
                chunk = bytearray(self.config.allocation_size_kb * 1024)
                self.allocations.append(chunk)
                allocated_mb += self.config.allocation_size_kb / 1024
                self.worker_count += 1
                time.sleep(self.config.allocation_interval_seconds)
            except MemoryError:
                logger.error("MemoryError during allocation - possible leak causing OOM")
                break

    def _memory_monitor(self) -> None:
        start_time = time.time()
        while self.running:
            rss_mb, vms_mb = self._get_memory_mb()
            gc_counts = self._get_gc_counts()

            snapshot = MemorySnapshot(
                timestamp=time.time() - start_time,
                rss_mb=rss_mb,
                vms_mb=vms_mb,
                gc_gen0=gc_counts[0],
                gc_gen1=gc_counts[1],
                gc_gen2=gc_counts[2],
            )
            self.snapshots.append(snapshot)
            logger.info(
                f"[{snapshot.timestamp:.1f}s] RSS: {rss_mb:.1f}MB, "
                f"VMS: {vms_mb:.1f}MB, GC: {gc_counts}"
            )
            time.sleep(self.config.sample_interval_seconds)

    def start(self) -> None:
        self.running = True
        import threading
        self.worker_thread = threading.Thread(target=self._allocation_worker, daemon=True)
        self.monitor_thread = threading.Thread(target=self._memory_monitor, daemon=True)
        self.worker_thread.start()
        self.monitor_thread.start()
        logger.info(f"Started soak test: {self.config.test_duration_seconds}s duration")

    def stop(self) -> list[MemorySnapshot]:
        self.running = False
        if hasattr(self, 'worker_thread') and self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        if hasattr(self, 'monitor_thread') and self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        return self.snapshots

    def get_allocated_mb(self) -> float:
        return sum(a.__len__() for a in self.allocations) / (1024 * 1024)

    def analyze_leak(self) -> dict:
        if len(self.snapshots) < 2:
            return {"leak_detected": False, "reason": "insufficient_data"}

        first = self.snapshots[0]
        last = self.snapshots[-1]
        duration_hours = (last.timestamp - first.timestamp) / 3600

        if duration_hours < 0.005:
            return {"leak_detected": False, "reason": "test_too_short"}

        rss_growth_mb = last.rss_mb - first.rss_mb
        leak_rate_mb_per_hour = (
            rss_growth_mb / duration_hours if duration_hours > 0 else 0
        )
        final_rss_exceeded = last.rss_mb > self.config.max_memory_mb

        return {
            "leak_detected": (
                leak_rate_mb_per_hour > self.config.leak_threshold_mb_per_hour
                or final_rss_exceeded
            ),
            "rss_start_mb": first.rss_mb,
            "rss_end_mb": last.rss_mb,
            "rss_growth_mb": rss_growth_mb,
            "duration_hours": duration_hours,
            "leak_rate_mb_per_hour": leak_rate_mb_per_hour,
            "threshold_mb_per_hour": self.config.leak_threshold_mb_per_hour,
            "final_rss_exceeded": final_rss_exceeded,
            "allocations_performed": self.worker_count,
            "total_allocated_mb": self.get_allocated_mb(),
        }


@pytest.fixture
def soak_config() -> SoakTestConfig:
    return SoakTestConfig(
        test_duration_seconds=60,
        allocation_interval_seconds=0.1,
        allocation_size_kb=1024,
        leak_threshold_mb_per_hour=200.0,
        max_memory_mb=850.0,
        sample_interval_seconds=2.0,
    )


def test_memory_leak_soak_short(soak_config: SoakTestConfig):
    test = MemoryLeakSoakTest(soak_config)
    test.start()
    time.sleep(soak_config.test_duration_seconds)
    snapshots = test.stop()

    assert len(snapshots) >= 2, "Should capture at least 2 memory snapshots"

    analysis = test.analyze_leak()
    logger.info(f"Memory leak analysis: {analysis}")

    if analysis.get("final_rss_exceeded"):
        pytest.fail(f"Memory exceeded max: {snapshots[-1].rss_mb:.1f}MB")


def test_memory_growth_rate_calculation(soak_config: SoakTestConfig):
    test = MemoryLeakSoakTest(soak_config)
    test.start()
    time.sleep(40)
    test.stop()

    analysis = test.analyze_leak()
    assert "rss_growth_mb" in analysis
    assert "duration_hours" in analysis
    assert "leak_rate_mb_per_hour" in analysis
    assert "allocations_performed" in analysis


def test_memory_snapshot_integrity(soak_config: SoakTestConfig):
    test = MemoryLeakSoakTest(soak_config)
    test.start()
    time.sleep(20)
    snapshots = test.stop()

    for snap in snapshots:
        assert snap.timestamp >= 0
        assert snap.rss_mb > 0
        assert snap.vms_mb > 0
        assert len((snap.gc_gen0, snap.gc_gen1, snap.gc_gen2)) == 3

    timestamps = [s.timestamp for s in snapshots]
    msg = "Snapshots should be in chronological order"
    assert timestamps == sorted(timestamps), msg


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
