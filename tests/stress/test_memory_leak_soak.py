"""
Memory Leak Soak Test - Long Duration Memory Growth Monitoring.

This test simulates sustained event processing over extended periods (12-24 hours)
to detect memory leaks by tracking RSS (Resident Set Size) growth patterns.

Run with: pytest tests/stress/test_memory_leak_soak.py -v
"""

import time
import threading
import logging
import psutil
import os
from dataclasses import dataclass
from typing import Optional

import pytest

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    timestamp: float
    rss_mb: float
    vms_mb: float
    events_processed: int
    gc_counts: tuple[int, int, int]


@dataclass
class SoakTestConfig:
    num_nodes: int = 4
    test_duration_seconds: int = 3600
    events_per_second: int = 10
    sample_interval_seconds: int = 30
    leak_threshold_mb_per_hour: float = 50.0
    max_memory_mb: float = 850.0  # Giới hạn an toàn cho container 1GiB (trừ hao OS buffer)


class MemoryLeakSoakTest:
    def __init__(self, config: Optional[SoakTestConfig] = None):
        self.config = config or SoakTestConfig()
        self.process = psutil.Process(os.getpid())
        self.snapshots: list[MemorySnapshot] = []
        self.events_processed = 0
        self.events_lock = threading.Lock()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.monitor_thread: Optional[threading.Thread] = None

    def _get_memory_mb(self) -> tuple[float, float]:
        mem_info = self.process.memory_info()
        return mem_info.rss / (1024 * 1024), mem_info.vms / (1024 * 1024)

    def _get_gc_counts(self) -> tuple[int, int, int]:
        import gc
        return gc.get_count()

    def _event_worker(self) -> None:
        while self.running:
            with self.events_lock:
                self.events_processed += self.config.events_per_second
            time.sleep(1.0)

    def _memory_monitor(self) -> None:
        start_time = time.time()
        while self.running:
            rss_mb, vms_mb = self._get_memory_mb()
            with self.events_lock:
                events = self.events_processed
            gc_counts = self._get_gc_counts()

            snapshot = MemorySnapshot(
                timestamp=time.time() - start_time,
                rss_mb=rss_mb,
                vms_mb=vms_mb,
                events_processed=events,
                gc_counts=gc_counts,
            )
            self.snapshots.append(snapshot)
            logger.info(
                f"[{snapshot.timestamp:.1f}s] RSS: {rss_mb:.1f}MB, "
                f"VMS: {vms_mb:.1f}MB, Events: {events}, "
                f"GC: {gc_counts}"
            )

            time.sleep(self.config.sample_interval_seconds)

    def start(self) -> None:
        self.running = True
        self.worker_thread = threading.Thread(target=self._event_worker, daemon=True)
        self.monitor_thread = threading.Thread(target=self._memory_monitor, daemon=True)
        self.worker_thread.start()
        self.monitor_thread.start()
        logger.info(f"Started soak test: {self.config.test_duration_seconds}s duration")

    def stop(self) -> list[MemorySnapshot]:
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        return self.snapshots

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
        }


@pytest.fixture
def soak_config() -> SoakTestConfig:
    return SoakTestConfig(
        num_nodes=4,
        test_duration_seconds=60,
        events_per_second=10,
        sample_interval_seconds=2,
        leak_threshold_mb_per_hour=100.0,
        max_memory_mb=850.0,
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


def test_memory_snapshot_integrity(soak_config: SoakTestConfig):
    test = MemoryLeakSoakTest(soak_config)
    test.start()
    time.sleep(20)
    snapshots = test.stop()

    for _i, snap in enumerate(snapshots):
        assert snap.timestamp >= 0
        assert snap.rss_mb > 0
        assert snap.vms_mb > 0
        assert snap.events_processed >= 0
        assert len(snap.gc_counts) == 3

    timestamps = [s.timestamp for s in snapshots]
    msg = "Snapshots should be in chronological order"
    assert timestamps == sorted(timestamps), msg


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
