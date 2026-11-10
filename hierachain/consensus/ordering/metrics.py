"""
Ordering metrics and statistics for the HieraChain ordering service.
"""

import threading
from typing import Any


class OrderingMetrics:
    """Collector for ordering service statistics and metrics"""
    def __init__(self):
        self.statistics: dict[str, int | float] = {
            "events_received": 0,
            "events_certified": 0,
            "events_rejected": 0,
            "blocks_created": 0,
            "average_batch_size": 0.0,
            "average_processing_time": 0.0,
            "total_latency": 0.0,
            "events_committed": 0
        }
        self._lock = threading.Lock()

    def record_received(self) -> None:
        with self._lock:
            self.statistics["events_received"] += 1

    def record_certified(self) -> None:
        with self._lock:
            self.statistics["events_certified"] += 1

    def record_rejected(self) -> None:
        with self._lock:
            self.statistics["events_rejected"] += 1

    def record_block_created(self, event_count: int, block_latency: float) -> None:
        with self._lock:
            self.statistics["blocks_created"] += 1
            self.statistics["total_latency"] += block_latency
            self.statistics["events_committed"] += event_count

            if self.statistics["events_committed"] > 0:
                self.statistics["average_processing_time"] = (
                    self.statistics["total_latency"] / self.statistics["events_committed"]
                )

            blocks = self.statistics["blocks_created"]
            prev_avg = self.statistics["average_batch_size"]
            total_events = prev_avg * (blocks - 1) + event_count
            self.statistics["average_batch_size"] = total_events / blocks

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return self.statistics.copy()
