"""
Deadlock detection for HieraChain Ledger.

Monitors lock wait times and detects potential deadlocks,
providing timeout-based lock acquisition and recovery callbacks.
"""

import time
import logging
import threading
from typing import Any, cast

logger = logging.getLogger(__name__)


class DeadlockDetector:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._lock_wait_times: dict[int, list[float]] = {}
        self._monitor_thread: threading.Thread | None = None
        self._threshold = 3.0
        self._deadlock_callbacks: list[Any] = []

    def record_wait_start(self, lock_id: int) -> float:
        self._lock_wait_times[lock_id] = self._lock_wait_times.get(lock_id, [])
        self._lock_wait_times[lock_id].append(time.time())
        return self._lock_wait_times[lock_id][-1]

    def record_wait_end(self, lock_id: int, wait_time: float) -> None:
        if lock_id in self._lock_wait_times and self._lock_wait_times[lock_id]:
            self._lock_wait_times[lock_id].pop(0)
            if wait_time > self._threshold:
                logger.warning(
                    "DEADLOCK RISK: Lock %d waited %.2fs (threshold=%.2fs)",
                    lock_id, wait_time, self._threshold
                )
                self._trigger_deadlock_recovery(lock_id, wait_time)

    def _trigger_deadlock_recovery(self, lock_id: int, wait_time: float) -> None:
        for callback in self._deadlock_callbacks:
            try:
                callback(lock_id, wait_time)
            except Exception as e:
                logger.error("Deadlock recovery callback failed: %s", e)

    def get_lock_stats(self) -> dict[int, dict[str, Any]]:
        stats = {}
        for lock_id, wait_times in self._lock_wait_times.items():
            if wait_times:
                current_wait = time.time() - wait_times[0]
                stats[lock_id] = {
                    "waiting": len(wait_times),
                    "current_wait": current_wait,
                    "at_risk": current_wait > self._threshold
                }
        return stats


_deadlock_detector: DeadlockDetector | None = None


def get_deadlock_detector() -> DeadlockDetector:
    global _deadlock_detector
    if _deadlock_detector is None:
        _deadlock_detector = DeadlockDetector()
    return cast(DeadlockDetector, _deadlock_detector)
