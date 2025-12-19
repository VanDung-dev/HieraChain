"""
Performance Metrics for HieraChain Data Operations

This module provides performance tracking for Arrow data operations,
including storage, conversion, and query operations.
"""

import time
import logging
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricSample:
    """A single metric measurement."""
    timestamp: float
    duration_ms: float
    data_size_bytes: int = 0
    row_count: int = 0
    operation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricAggregation:
    """Aggregated statistics for a metric."""
    count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    total_bytes: int = 0
    total_rows: int = 0
    
    @property
    def avg_duration_ms(self) -> float:
        """Average duration in milliseconds."""
        return self.total_duration_ms / self.count if self.count > 0 else 0.0
    
    @property
    def throughput_rows_per_sec(self) -> float:
        """Rows processed per second."""
        total_seconds = self.total_duration_ms / 1000
        return self.total_rows / total_seconds if total_seconds > 0 else 0.0
    
    @property
    def throughput_bytes_per_sec(self) -> float:
        """Bytes processed per second."""
        total_seconds = self.total_duration_ms / 1000
        return self.total_bytes / total_seconds if total_seconds > 0 else 0.0
    
    def add_sample(self, sample: MetricSample) -> None:
        """Add a sample to the aggregation."""
        self.count += 1
        self.total_duration_ms += sample.duration_ms
        self.min_duration_ms = min(self.min_duration_ms, sample.duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, sample.duration_ms)
        self.total_bytes += sample.data_size_bytes
        self.total_rows += sample.row_count
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "count": self.count,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.count > 0 else 0,
            "max_duration_ms": round(self.max_duration_ms, 2),
            "total_bytes": self.total_bytes,
            "total_rows": self.total_rows,
            "throughput_rows_per_sec": round(self.throughput_rows_per_sec, 2),
            "throughput_bytes_per_sec": round(self.throughput_bytes_per_sec, 2)
        }


class PerformanceMetrics:
    """
    Singleton class for collecting and aggregating performance metrics.
    
    Thread-safe metric collection for data operations.
    
    Usage:
        metrics = PerformanceMetrics.get_instance()
        
        with metrics.measure("arrow_conversion", row_count=1000):
            # ... operation ...
        
        # Or use decorator
        @metrics.track_performance("block_storage")
        def store_block(...):
            ...
    """
    
    _instance: Optional['PerformanceMetrics'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'PerformanceMetrics':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._metrics: dict[str, MetricAggregation] = defaultdict(MetricAggregation)
        self._samples: dict[str, list[MetricSample]] = defaultdict(list)
        self._sample_limit = 1000  # Keep last N samples per operation
        self._data_lock = threading.Lock()
        self._enabled = True
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'PerformanceMetrics':
        """Get the singleton instance."""
        return cls()
    
    def enable(self) -> None:
        """Enable metric collection."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable metric collection."""
        self._enabled = False
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._data_lock:
            self._metrics.clear()
            self._samples.clear()
    
    def record(
        self,
        operation: str,
        duration_ms: float,
        data_size_bytes: int = 0,
        row_count: int = 0,
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Record a metric sample.
        
        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            data_size_bytes: Size of data processed
            row_count: Number of rows processed
            metadata: Additional metadata
        """
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
            
            # Trim old samples
            if len(samples) > self._sample_limit:
                self._samples[operation] = samples[-self._sample_limit:]
    
    @contextmanager
    def measure(
        self,
        operation: str,
        data_size_bytes: int = 0,
        row_count: int = 0,
        metadata: Optional[dict[str, Any]] = None
    ):
        """
        Context manager to measure operation duration.
        
        Usage:
            with metrics.measure("my_operation", row_count=100):
                # ... do work ...
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.record(
                operation=operation,
                duration_ms=duration_ms,
                data_size_bytes=data_size_bytes,
                row_count=row_count,
                metadata=metadata
            )
    
    def track_performance(
        self,
        operation: str
    ) -> Callable:
        """
        Decorator to track function performance.
        
        Usage:
            @metrics.track_performance("my_function")
            def my_function(data):
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Try to infer data size from result
                row_count = 0
                data_size = 0
                if hasattr(result, '__len__'):
                    row_count = len(result)
                
                self.record(
                    operation=operation,
                    duration_ms=duration_ms,
                    row_count=row_count,
                    data_size_bytes=data_size
                )
                return result
            return wrapper
        return decorator
    
    def get_metrics(self, operation: Optional[str] = None) -> dict[str, Any]:
        """
        Get aggregated metrics.
        
        Args:
            operation: Specific operation name, or None for all
            
        Returns:
            dictionary of metrics
        """
        with self._data_lock:
            if operation:
                if operation in self._metrics:
                    return {operation: self._metrics[operation].to_dict()}
                return {}
            
            return {
                name: agg.to_dict()
                for name, agg in self._metrics.items()
            }
    
    def get_recent_samples(
        self,
        operation: str,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Get recent samples for an operation.
        
        Args:
            operation: Operation name
            limit: Maximum samples to return
            
        Returns:
            List of sample dictionaries
        """
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
        """
        Get a complete summary of all metrics.
        
        Returns:
            Dictionary with full summary
        """
        with self._data_lock:
            summary = {
                "enabled": self._enabled,
                "operations_tracked": len(self._metrics),
                "total_samples": sum(
                    len(samples) for samples in self._samples.values()
                ),
                "metrics": self.get_metrics()
            }
            
            # Add top operations by duration
            if self._metrics:
                sorted_ops = sorted(
                    self._metrics.items(),
                    key=lambda x: x[1].total_duration_ms,
                    reverse=True
                )
                summary["top_by_duration"] = [
                    {"operation": name, "total_ms": round(agg.total_duration_ms, 2)}
                    for name, agg in sorted_ops[:5]
                ]
            
            return summary
    
    def log_summary(self) -> None:
        """Log a summary of metrics."""
        summary = self.get_summary()
        
        logger.info("=== Performance Metrics Summary ===")
        logger.info(f"Operations tracked: {summary['operations_tracked']}")
        logger.info(f"Total samples: {summary['total_samples']}")
        
        for name, metrics in summary.get('metrics', {}).items():
            logger.info(
                f"  {name}: count={metrics['count']}, "
                f"avg={metrics['avg_duration_ms']:.2f}ms, "
                f"throughput={metrics['throughput_rows_per_sec']:.2f} rows/sec"
            )


# Global convenience functions
def get_metrics_instance() -> PerformanceMetrics:
    """Get the global metrics instance."""
    return PerformanceMetrics.get_instance()


def track_arrow_conversion(row_count: int = 0):
    """Context manager for tracking Arrow conversion."""
    return get_metrics_instance().measure(
        "arrow_conversion",
        row_count=row_count
    )


def track_parquet_write(data_size_bytes: int = 0, row_count: int = 0):
    """Context manager for tracking Parquet writes."""
    return get_metrics_instance().measure(
        "parquet_write",
        data_size_bytes=data_size_bytes,
        row_count=row_count
    )


def track_parquet_read(data_size_bytes: int = 0):
    """Context manager for tracking Parquet reads."""
    return get_metrics_instance().measure(
        "parquet_read",
        data_size_bytes=data_size_bytes
    )


def track_query(operation: str = "query"):
    """Context manager for tracking query operations."""
    return get_metrics_instance().measure(operation)
