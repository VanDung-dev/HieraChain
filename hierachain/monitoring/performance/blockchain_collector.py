"""
Blockchain metrics collector for consensus, event rate and processing times.
"""

import time
import logging
import statistics
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


class BlockchainMetricsCollector:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.event_counts = defaultdict(int)
        self.block_creation_times: deque[dict[str, float]] = deque(maxlen=100)
        self.event_processing_times: deque[float] = deque(maxlen=1000)
        self.consensus_metrics = {
            'rounds': 0,
            'failures': 0,
            'avg_time': 0.0
        }
        self.last_collection_time = time.time()
        self.last_event_count = 0
        self.last_block_count = 0

    def record_event_processed(self, event_type: str, processing_time: float):
        self.event_counts[event_type] += 1
        self.event_processing_times.append(processing_time)

    def record_block_created(self, creation_time: float, block_size: int):
        self.block_creation_times.append({
            'time': creation_time,
            'size': block_size,
            'timestamp': time.time()
        })

    def record_consensus_round(self, duration: float, success: bool):
        self.consensus_metrics['rounds'] += 1
        if not success:
            self.consensus_metrics['failures'] += 1
        total_time = (
            self.consensus_metrics['avg_time'] * (self.consensus_metrics['rounds'] - 1)
        )
        self.consensus_metrics['avg_time'] = (
            (total_time + duration) / self.consensus_metrics['rounds']
        )

    def collect_metrics(self) -> dict[str, float]:
        try:
            current_time = time.time()
            time_diff = current_time - self.last_collection_time
            metrics = {}
            if self.event_processing_times:
                metrics.update({
                    'event_processing_avg_time': statistics.mean(
                        self.event_processing_times
                    ),
                    'event_processing_max_time': max(self.event_processing_times),
                    'event_processing_min_time': min(self.event_processing_times)
                })
            if self.block_creation_times:
                recent_blocks = [
                    b for b in self.block_creation_times
                    if current_time - b['timestamp'] <= 300
                ]
                if recent_blocks:
                    creation_times = [b['time'] for b in recent_blocks]
                    block_sizes = [b['size'] for b in recent_blocks]
                    metrics.update({
                        'block_creation_avg_time': statistics.mean(creation_times),
                        'block_creation_rate': len(recent_blocks) / 300.0,
                        'block_avg_size': statistics.mean(block_sizes)
                    })
            total_events = sum(self.event_counts.values())
            if time_diff > 0:
                event_rate = (total_events - self.last_event_count) / time_diff
                metrics['event_throughput'] = event_rate
                self.last_event_count = total_events
            metrics.update({
                'consensus_rounds_total': self.consensus_metrics['rounds'],
                'consensus_failures_total': self.consensus_metrics['failures'],
                'consensus_avg_time': self.consensus_metrics['avg_time'],
                'consensus_success_rate': (
                    (
                        self.consensus_metrics['rounds']
                        - self.consensus_metrics['failures']
                    ) / max(self.consensus_metrics['rounds'], 1)
                ) * 100
            })
            self.last_collection_time = current_time
            return metrics
        except Exception as e:
            self.logger.error(f"Error collecting blockchain metrics: {str(e)}")
            return {}
