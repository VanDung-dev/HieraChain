"""
Performance Monitoring Module for HieraChain Ledger.

"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from typing import Any

import psutil

from hierachain.monitoring.types import (
    MetricType,
    MetricUnit,
    PerformanceMetric,
)
from hierachain.serialization import dumps_json

logger = logging.getLogger(__name__)


# =====================================================================
# Blockchain Metrics Collector Component
# =====================================================================


class BlockchainMetricsCollector:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.event_counts = defaultdict(int)
        self.block_creation_times: deque[dict[str, float]] = deque(maxlen=100)
        self.event_processing_times: deque[float] = deque(maxlen=1000)
        self.consensus_metrics = {"rounds": 0, "failures": 0, "avg_time": 0.0}
        self.last_collection_time = time.time()
        self.last_event_count = 0
        self.last_block_count = 0

    def record_event_processed(self, event_type: str, processing_time: float) -> None:
        self.event_counts[event_type] += 1
        self.event_processing_times.append(processing_time)

    def record_block_created(self, creation_time: float, block_size: int) -> None:
        self.block_creation_times.append({"time": creation_time, "size": block_size, "timestamp": time.time()})

    def record_consensus_round(self, duration: float, success: bool) -> None:
        self.consensus_metrics["rounds"] += 1
        if not success:
            self.consensus_metrics["failures"] += 1
        total_time = self.consensus_metrics["avg_time"] * (self.consensus_metrics["rounds"] - 1)
        self.consensus_metrics["avg_time"] = (total_time + duration) / self.consensus_metrics["rounds"]

    def collect_metrics(self) -> dict[str, float]:
        try:
            current_time = time.time()
            time_diff = current_time - self.last_collection_time
            metrics = {}
            if self.event_processing_times:
                metrics.update(
                    {
                        "event_processing_avg_time": statistics.mean(self.event_processing_times),
                        "event_processing_max_time": max(self.event_processing_times),
                        "event_processing_min_time": min(self.event_processing_times),
                    }
                )
            if self.block_creation_times:
                recent_blocks = [b for b in self.block_creation_times if current_time - b["timestamp"] <= 300]
                if recent_blocks:
                    creation_times = [b["time"] for b in recent_blocks]
                    block_sizes = [b["size"] for b in recent_blocks]
                    metrics.update(
                        {
                            "block_creation_avg_time": statistics.mean(creation_times),
                            "block_creation_rate": len(recent_blocks) / 300.0,
                            "block_avg_size": statistics.mean(block_sizes),
                        }
                    )
            total_events = sum(self.event_counts.values())
            if time_diff > 0:
                event_rate = (total_events - self.last_event_count) / time_diff
                metrics["event_throughput"] = event_rate
                self.last_event_count = total_events
            metrics.update(
                {
                    "consensus_rounds_total": self.consensus_metrics["rounds"],
                    "consensus_failures_total": self.consensus_metrics["failures"],
                    "consensus_avg_time": self.consensus_metrics["avg_time"],
                    "consensus_success_rate": (
                        (self.consensus_metrics["rounds"] - self.consensus_metrics["failures"])
                        / max(self.consensus_metrics["rounds"], 1)
                    )
                    * 100,
                }
            )
            self.last_collection_time = current_time
            return metrics
        except Exception as e:
            self.logger.error(f"Error collecting blockchain metrics: {e!s}")
            return {}


# =====================================================================
# System Metrics Collector Component
# =====================================================================


class SystemMetricsCollector:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.process = psutil.Process()

    def collect_cpu_metrics(self) -> dict[str, float]:
        try:
            cpu_count = psutil.cpu_count()
            return {
                "cpu_usage_total": float(psutil.cpu_percent(interval=0.1)),
                "cpu_usage_process": float(self.process.cpu_percent()),
                "cpu_count": float(cpu_count if cpu_count is not None else 0),
                "load_average_1m": float(psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0.0),
            }
        except Exception as e:
            self.logger.error("Error collecting CPU metrics: %s", str(e))
            return {}

    def collect_memory_metrics(self) -> dict[str, float]:
        try:
            return _collect_memory_psutil(self)
        except Exception as e:
            self.logger.error("Error collecting memory metrics: %s", str(e))
            return {}

    def collect_disk_metrics(self) -> dict[str, float]:
        try:
            return _collect_disk_psutil()
        except Exception as e:
            self.logger.error("Error collecting disk metrics: %s", str(e))
            return {}

    def collect_network_metrics(self) -> dict[str, float]:
        try:
            return _collect_network_psutil()
        except Exception as e:
            self.logger.error("Error collecting network metrics: %s", str(e))
            return {}


def _collect_memory_psutil(collector: SystemMetricsCollector) -> dict[str, float]:
    virtual_memory = psutil.virtual_memory()
    process_memory = collector.process.memory_info()
    return {
        "memory_usage_percent": float(virtual_memory.percent),
        "memory_total": float(virtual_memory.total),
        "memory_available": float(virtual_memory.available),
        "memory_used": float(virtual_memory.used),
        "process_memory_rss": float(process_memory.rss),
        "process_memory_vms": float(process_memory.vms),
    }


def _collect_disk_psutil() -> dict[str, float]:
    disk_usage = psutil.disk_usage("/")
    disk_io = psutil.disk_io_counters()
    metrics = {
        "disk_usage_percent": (disk_usage.used / disk_usage.total) * 100,
        "disk_total": disk_usage.total,
        "disk_free": disk_usage.free,
        "disk_used": disk_usage.used,
    }
    if disk_io:
        metrics.update(
            {
                "disk_read_bytes": float(disk_io.read_bytes),
                "disk_write_bytes": float(disk_io.write_bytes),
                "disk_read_count": float(disk_io.read_count),
                "disk_write_count": float(disk_io.write_count),
            }
        )
    return metrics


def _collect_network_psutil() -> dict[str, float]:
    network_io = psutil.net_io_counters()
    network_connections = len(psutil.net_connections())
    return {
        "network_bytes_sent": float(network_io.bytes_sent),
        "network_bytes_recv": float(network_io.bytes_recv),
        "network_packets_sent": float(network_io.packets_sent),
        "network_packets_recv": float(network_io.packets_recv),
        "network_connections_count": float(network_connections),
    }


# =====================================================================
# PerformanceMonitor Component
# =====================================================================


class PerformanceMonitor:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.system_collector = SystemMetricsCollector()
        self.blockchain_collector = BlockchainMetricsCollector()
        self.metrics: dict[str, PerformanceMetric] = {}
        self._initialize_default_metrics()
        self.collection_interval = self.config.get("collection_interval", 5.0)
        self.enable_alerts = self.config.get("enable_alerts", True)
        self.alert_handlers: list[Callable[[str, PerformanceMetric, float], None]] = []
        self.monitoring_active = False
        self.monitoring_thread: threading.Thread | None = None
        self.shutdown_event = threading.Event()
        self.custom_metrics_callbacks: dict[str, Callable[[], dict[str, float]]] = {}

    def add_custom_metric(
        self,
        name: str,
        metric_type: MetricType,
        unit: MetricUnit,
        description: str,
        threshold_warning: float | None = None,
        threshold_critical: float | None = None,
        callback: Callable[[], float] | None = None,
    ) -> None:
        self.metrics[name] = PerformanceMetric(
            name=name,
            metric_type=metric_type,
            unit=unit,
            description=description,
            threshold_warning=threshold_warning,
            threshold_critical=threshold_critical,
        )
        if callback:
            self.custom_metrics_callbacks[name] = lambda: {name: callback()}
        self.logger.info("Added custom metric: %s", name)

    def add_alert_handler(self, handler: Callable[[str, PerformanceMetric, float], None]) -> None:
        self.alert_handlers.append(handler)

    def record_blockchain_event(self, event_type: str, processing_time: float) -> None:
        self.blockchain_collector.record_event_processed(event_type, processing_time)

    def record_block_creation(self, creation_time: float, block_size: int) -> None:
        self.blockchain_collector.record_block_created(creation_time, block_size)

    def record_consensus_round(self, duration: float, success: bool) -> None:
        self.blockchain_collector.record_consensus_round(duration, success)

    def start_monitoring(self) -> None:
        if self.monitoring_active:
            self.logger.warning("Performance monitoring is already active")
            return
        self.monitoring_active = True
        self.shutdown_event.clear()
        thread = threading.Thread(
            target=self._monitoring_loop,
            name="PerformanceMonitor",
        )
        thread.daemon = True
        self.monitoring_thread = thread
        thread.start()
        self.logger.info("Performance monitoring started")

    def stop_monitoring(self) -> None:
        if not self.monitoring_active:
            return
        self.monitoring_active = False
        self.shutdown_event.set()
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10)
        self.logger.info("Performance monitoring stopped")

    def generate_report(self, format_type: str = "json") -> str:
        current_metrics = self.get_current_metrics()
        if format_type.lower() == "json":
            return self._generate_json_report(current_metrics)
        elif format_type.lower() == "text":
            return self._generate_text_report(current_metrics)
        else:
            raise ValueError(f"Unsupported report format: {format_type}")

    def _initialize_default_metrics(self) -> None:
        self.metrics.update(
            {
                "cpu_usage": PerformanceMetric(
                    name="cpu_usage",
                    metric_type=MetricType.SYSTEM,
                    unit=MetricUnit.PERCENTAGE,
                    description="CPU usage percentage",
                    threshold_warning=80.0,
                    threshold_critical=90.0,
                ),
                "memory_usage": PerformanceMetric(
                    name="memory_usage",
                    metric_type=MetricType.SYSTEM,
                    unit=MetricUnit.PERCENTAGE,
                    description="Memory usage percentage",
                    threshold_warning=85.0,
                    threshold_critical=95.0,
                ),
                "disk_usage": PerformanceMetric(
                    name="disk_usage",
                    metric_type=MetricType.SYSTEM,
                    unit=MetricUnit.PERCENTAGE,
                    description="Disk usage percentage",
                    threshold_warning=80.0,
                    threshold_critical=90.0,
                ),
                "network_connections": PerformanceMetric(
                    name="network_connections",
                    metric_type=MetricType.NETWORK,
                    unit=MetricUnit.COUNT,
                    description="Number of network connections",
                    threshold_warning=1000,
                    threshold_critical=2000,
                ),
                "event_throughput": PerformanceMetric(
                    name="event_throughput",
                    metric_type=MetricType.BLOCKCHAIN,
                    unit=MetricUnit.RATE,
                    description="Events processed per second",
                    threshold_warning=None,
                    threshold_critical=1.0,
                ),
                "block_creation_time": PerformanceMetric(
                    name="block_creation_time",
                    metric_type=MetricType.BLOCKCHAIN,
                    unit=MetricUnit.SECONDS,
                    description="Average block creation time",
                    threshold_warning=30.0,
                    threshold_critical=60.0,
                ),
                "consensus_success_rate": PerformanceMetric(
                    name="consensus_success_rate",
                    metric_type=MetricType.CONSENSUS,
                    unit=MetricUnit.PERCENTAGE,
                    description="Consensus success rate",
                    threshold_warning=95.0,
                    threshold_critical=90.0,
                    low_is_bad=True,
                ),
                "event_processing_time": PerformanceMetric(
                    name="event_processing_time",
                    metric_type=MetricType.BLOCKCHAIN,
                    unit=MetricUnit.SECONDS,
                    description="Average event processing time",
                    threshold_warning=1.0,
                    threshold_critical=5.0,
                ),
            }
        )

    def _monitoring_loop(self) -> None:
        while self.monitoring_active and not self.shutdown_event.is_set():
            self._execute_monitoring_cycle()
            if self.shutdown_event.wait(self.collection_interval):
                break

    def _execute_monitoring_cycle(self) -> None:
        try:
            self._collect_all_metrics()
            self._check_thresholds()
        except Exception as cycle_error:
            self.logger.error("Error in monitoring cycle: %s", str(cycle_error))

    def _collect_all_metrics(self) -> None:
        try:
            self._collect_system_metrics()
            self._collect_blockchain_metrics()
            self._collect_custom_metrics()
        except Exception as collect_error:
            self.logger.error("Error collecting all metrics: %s", str(collect_error))

    def _collect_system_metrics(self) -> None:
        system_metrics = self.system_collector.collect_cpu_metrics()
        system_metrics.update(self.system_collector.collect_memory_metrics())
        system_metrics.update(self.system_collector.collect_disk_metrics())
        system_metrics.update(self.system_collector.collect_network_metrics())
        self._apply_metric_mapping(
            system_metrics,
            {
                "cpu_usage_total": "cpu_usage",
                "memory_usage_percent": "memory_usage",
                "disk_usage_percent": "disk_usage",
                "network_connections_count": "network_connections",
            },
        )

    def _collect_blockchain_metrics(self) -> None:
        blockchain_metrics = self.blockchain_collector.collect_metrics()
        self._apply_metric_mapping(
            blockchain_metrics,
            {
                "event_throughput": "event_throughput",
                "block_creation_avg_time": "block_creation_time",
                "consensus_success_rate": "consensus_success_rate",
                "event_processing_avg_time": "event_processing_time",
            },
        )

    def _collect_custom_metrics(self) -> None:
        for callback_name, callback in self.custom_metrics_callbacks.items():
            try:
                for metric_name, value in callback().items():
                    if metric_name in self.metrics:
                        self.metrics[metric_name].add_value(value)
            except Exception as e:
                self.logger.error("Error collecting custom metric %s: %s", callback_name, str(e))

    def _apply_metric_mapping(self, source_metrics: dict[str, float], mapping: dict[str, str]) -> None:
        for source_key, internal_name in mapping.items():
            if source_key in source_metrics and internal_name in self.metrics:
                self.metrics[internal_name].add_value(source_metrics[source_key])

    def _check_thresholds(self) -> None:
        if not self.enable_alerts:
            return
        for metric_name, metric in self.metrics.items():
            try:
                exceeded, level = metric.is_threshold_exceeded()
                if not exceeded or level not in ["warning", "critical"]:
                    continue
                current_value = metric.get_current_value()
                if current_value is None:
                    continue
                for handler in self.alert_handlers:
                    try:
                        handler(level, metric, current_value)
                    except Exception as e:
                        self.logger.error("Alert handler error: %s", str(e))
                threshold = metric.threshold_critical if level == "critical" else metric.threshold_warning
                self.logger.warning(
                    "Performance alert: %s = %s (%s threshold: %s)", metric_name, current_value, level, threshold
                )
            except Exception as e:
                self.logger.error("Error checking threshold for %s: %s", metric_name, str(e))

    def get_current_metrics(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for name, metric in self.metrics.items():
            current_value = metric.get_current_value()
            result[name] = {
                "current_value": current_value,
                "unit": metric.unit.value,
                "description": metric.description,
                "type": metric.metric_type.value,
                "threshold_warning": metric.threshold_warning,
                "threshold_critical": metric.threshold_critical,
                "avg_5min": metric.get_average(300),
                "avg_1hour": metric.get_average(3600),
                "max_5min": metric.get_max(300),
                "data_points": len(metric.values) if metric.values else 0,
                "status": metric.is_threshold_exceeded()[1],
            }
        return result

    def get_metric_history(self, metric_name: str, duration_seconds: int | None = None) -> list[dict[str, Any]]:
        if metric_name not in self.metrics:
            return []
        metric = self.metrics[metric_name]
        if duration_seconds is None:
            values = list(metric.values) if metric.values else []
        else:
            cutoff_time = time.time() - duration_seconds
            values = [v for v in metric.values if v.timestamp >= cutoff_time] if metric.values else []
        return [asdict(v) for v in values]

    def _generate_json_report(self, current_metrics: dict[str, Any]) -> str:
        report_data = {
            "timestamp": time.time(),
            "monitoring_status": "active" if self.monitoring_active else "inactive",
            "metrics": current_metrics,
            "summary": _calculate_report_summary(current_metrics),
        }
        return dumps_json(report_data, indent=2, default=str)

    def _generate_text_report(self, current_metrics: dict[str, Any]) -> str:
        lines = [
            "Performance Monitoring Report",
            "=" * 50,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Status: {'Active' if self.monitoring_active else 'Inactive'}",
            "",
        ]
        metrics_by_type = _group_metrics_by_type(current_metrics)
        for metric_type, metrics in metrics_by_type.items():
            _add_type_section_to_report(lines, metric_type, metrics)
        return "\n".join(lines)

    def get_health_score(self) -> tuple[float, str]:
        if not self.metrics:
            return 0.0, "no_data"
        scores: list[float] = []
        critical_issues = 0
        warning_issues = 0
        for metric in self.metrics.values():
            _, level = metric.is_threshold_exceeded()
            if level == "critical":
                scores.append(0.0)
                critical_issues += 1
            elif level == "warning":
                scores.append(50.0)
                warning_issues += 1
            elif level == "normal":
                scores.append(100.0)
        if not scores:
            return 0.0, "no_data"
        avg_score = statistics.mean(scores)
        return avg_score, _determine_health_status(avg_score, critical_issues, warning_issues)


def _calculate_report_summary(current_metrics: dict[str, Any]) -> dict[str, int]:
    return {
        "total_metrics": len(current_metrics),
        "critical_alerts": len([m for m in current_metrics.values() if m["status"] == "critical"]),
        "warning_alerts": len([m for m in current_metrics.values() if m["status"] == "warning"]),
        "normal_metrics": len([m for m in current_metrics.values() if m["status"] == "normal"]),
    }


def _group_metrics_by_type(current_metrics: dict[str, Any]) -> dict[str, list]:
    metrics_by_type = defaultdict(list)
    for name, data in current_metrics.items():
        metrics_by_type[data["type"]].append((name, data))
    return metrics_by_type


def _get_status_symbol(status: str) -> str:
    return {"normal": "✓", "warning": "⚠", "critical": "✗", "no_data": "-"}.get(status, "?")


def _add_type_section_to_report(lines: list[str], metric_type: str, metrics: list) -> None:
    lines.append(f"\n{metric_type.upper()} METRICS:")
    lines.append("-" * 30)
    for name, data in metrics:
        status_symbol = _get_status_symbol(data["status"])
        lines.append(f"  {status_symbol} {name}: {data['current_value']} {data['unit']}")
        if data["status"] in ["warning", "critical"]:
            threshold = data.get(f"threshold_{data['status']}")
            if threshold:
                lines.append(f"    ({data['status']} threshold: {threshold})")


def _determine_health_status(avg_score: float, critical_issues: int, warning_issues: int) -> str:
    if critical_issues > 0:
        return "critical"
    if warning_issues > 0:
        return "warning"
    if avg_score >= 90:
        return "excellent"
    if avg_score >= 70:
        return "good"
    return "poor"


def create_default_alert_handler() -> Callable[[str, PerformanceMetric, float], None]:
    def alert_handler(level: str, metric: PerformanceMetric, value: float) -> None:
        log = logging.getLogger("PerformanceMonitor.Alerts")
        log.warning(
            "Performance alert: %s = %s %s (threshold: %s) - %s",
            metric.name,
            value,
            metric.unit.value,
            getattr(metric, f"threshold_{level}", "unknown"),
            metric.description,
        )

    return alert_handler
