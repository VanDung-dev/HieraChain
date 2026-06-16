"""
Performance Metrics for HieraChain Data Operations

Provides performance tracking for Arrow data operations,
including storage, conversion, and query operations.
"""

from __future__ import annotations

import time
import logging
import threading
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable

from hierachain.monitoring.types import MetricSample, MetricAggregation

logger = logging.getLogger(__name__)

__all__ = [
    "MetricSample",
    "MetricAggregation",
    "PerformanceMetrics",
    "get_metrics_instance",
    "track_arrow_conversion",
    "track_parquet_write",
    "track_parquet_read",
    "track_query",
]


class PerformanceMetrics:
    _instance: PerformanceMetrics | None = None
    _lock = threading.Lock()

    def __new__(cls) -> 'PerformanceMetrics':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        if cls._instance is None:
            raise RuntimeError("PerformanceMetrics singleton initialization failed")
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._metrics: dict[str, MetricAggregation] = defaultdict(MetricAggregation)
        self._samples: dict[str, list[MetricSample]] = defaultdict(list)
        self._sample_limit = 1000
        self._data_lock = threading.Lock()
        self._enabled = True
        self._initialized = True

    @classmethod
    def get_instance(cls) -> 'PerformanceMetrics':
        return cls()

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def reset(self) -> None:
        with self._data_lock:
            self._metrics.clear()
            self._samples.clear()

    def record(
        self, operation: str, duration_ms: float,
        data_size_bytes: int = 0, row_count: int = 0,
        metadata: dict[str, Any] | None = None
    ) -> None:
        if not self._enabled:
            return
        sample = MetricSample(
            timestamp=time.time(),
            duration_ms=duration_ms,
            data_size_bytes=data_size_bytes,
            row_count=row_count,
            operation=operation,
            metadata=metadata or {}
        )
        with self._data_lock:
            self._metrics[operation].add_sample(sample)
            samples = self._samples[operation]
            samples.append(sample)
            if len(samples) > self._sample_limit:
                self._samples[operation] = samples[-self._sample_limit:]

    @contextmanager
    def measure(
        self, operation: str, data_size_bytes: int = 0,
        row_count: int = 0, metadata: dict[str, Any] | None = None
    ):
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.record(
                operation=operation, duration_ms=duration_ms,
                data_size_bytes=data_size_bytes, row_count=row_count,
                metadata=metadata
            )

    def track_performance(self, operation: str) -> Callable:
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                row_count = 0
                data_size = 0
                if hasattr(result, '__len__'):
                    row_count = len(result)
                self.record(
                    operation=operation, duration_ms=duration_ms,
                    row_count=row_count, data_size_bytes=data_size
                )
                return result
            return wrapper
        return decorator

    def get_metrics(self, operation: str | None = None) -> dict[str, Any]:
        with self._data_lock:
            if operation:
                if operation in self._metrics:
                    return {operation: self._metrics[operation].to_dict()}
                return {}
            return {
                name: agg.to_dict()
                for name, agg in self._metrics.items()
            }

    def get_recent_samples(self, operation: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._data_lock:
            samples = self._samples.get(operation, [])[-limit:]
            return [
                {
                    "timestamp": s.timestamp,
                    "duration_ms": round(s.duration_ms, 2),
                    "data_size_bytes": s.data_size_bytes,
                    "row_count": s.row_count,
                    "metadata": s.metadata
                }
                for s in samples
            ]

    def get_summary(self) -> dict[str, Any]:
        with self._data_lock:
            summary: dict[str, Any] = {
                "enabled": self._enabled,
                "operations_tracked": len(self._metrics),
                "total_samples": sum(
                    len(samples) for samples in self._samples.values()
                ),
                "metrics": self.get_metrics()
            }
            if self._metrics:
                sorted_ops = sorted(
                    self._metrics.items(),
                    key=lambda x: x[1].total_duration_ms,
                    reverse=True
                )
                summary["top_by_duration"] = [
                    {
                        "operation": name,
                        "total_duration_ms": round(agg.total_duration_ms, 2),
                        "avg_duration_ms": round(agg.avg_duration_ms, 2),
                        "count": agg.count
                    }
                    for name, agg in sorted_ops[:5]
                ]
            return summary

    def log_summary(self) -> None:
        summary = self.get_summary()
        logger.info("=== Performance Metrics Summary ===")
        logger.info("Operations tracked: %d", summary['operations_tracked'])
        logger.info("Total samples: %d", summary['total_samples'])
        for name, metrics in summary.get('metrics', {}).items():
            logger.info(
                f"  {name}: count={metrics['count']}, "
                f"avg={metrics['avg_duration_ms']:.2f}ms, "
                f"throughput={metrics['throughput_rows_per_sec']:.2f} rows/sec"
            )


def get_metrics_instance() -> PerformanceMetrics:
    return PerformanceMetrics.get_instance()


def track_arrow_conversion(row_count: int = 0):
    metrics = get_metrics_instance()
    return PerformanceMetrics.measure(
        metrics, operation="arrow_conversion", row_count=row_count,
    )


def track_parquet_write(data_size_bytes: int = 0, row_count: int = 0):
    metrics = get_metrics_instance()
    return PerformanceMetrics.measure(
        metrics, operation="parquet_write",
        data_size_bytes=data_size_bytes, row_count=row_count,
    )


def track_parquet_read(data_size_bytes: int = 0):
    metrics = get_metrics_instance()
    return PerformanceMetrics.measure(
        metrics, operation="parquet_read", data_size_bytes=data_size_bytes,
    )


def track_query(operation: str = "query"):
    metrics = get_metrics_instance()
    return PerformanceMetrics.measure(metrics, operation=operation)
