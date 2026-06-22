"""
Anomaly detection algorithm for risk management and performance metrics.
"""

import time
import statistics
from collections import deque, defaultdict


class AnomalyDetector:
    def __init__(self, window_size: int = 100, sensitivity: float = 2.0) -> None:
        self.window_size = window_size
        self.sensitivity = sensitivity
        self.metric_histories: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

    def add_data_point(self, metric_name: str, value: float) -> None:
        self.metric_histories[metric_name].append(
            {'timestamp': time.time(), 'value': value}
        )

    def is_anomaly(self, metric_name: str, value: float) -> tuple[bool, float]:
        history = self.metric_histories[metric_name]
        if len(history) < 10:
            return False, 0.0
        values = [point['value'] for point in history]
        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values)
            if stdev == 0:
                return False, 0.0
            z_score = abs((value - mean) / stdev)
            return z_score > self.sensitivity, z_score
        except statistics.StatisticsError:
            return False, 0.0
