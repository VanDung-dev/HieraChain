"""
Performance Monitoring Module for HieraChain Framework

This module provides comprehensive real-time performance monitoring capabilities
for tracking system health, resource usage, and performance metrics. Supports
CPU, memory, throughput, and custom metrics.
"""

import time
import threading
import logging
import statistics
import json
import psutil
from typing import Any, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque, defaultdict
from datetime import datetime


class MetricType(Enum):
    """Types of performance metrics"""
    SYSTEM = "system"
    BLOCKCHAIN = "blockchain"
    CONSENSUS = "consensus"
    SECURITY = "security"
    STORAGE = "storage"
    NETWORK = "network"
    CUSTOM = "custom"


class MetricUnit(Enum):
    """Metric measurement units"""
    PERCENTAGE = "percentage"
    BYTES = "bytes"
    SECONDS = "seconds"
    COUNT = "count"
    RATE = "rate"  # per second
    THROUGHPUT = "throughput"  # operations per second


@dataclass
class MetricValue:
    """Single metric measurement"""
    timestamp: float
    value: float
    unit: MetricUnit
    metadata: dict[str, Any] | None = None


@dataclass
class PerformanceMetric:
    """Performance metric definition and history"""
    name: str
    metric_type: MetricType
    unit: MetricUnit
    description: str
    threshold_warning: float | None = None
    threshold_critical: float | None = None
    history_size: int = 1000
    values: deque | None = None
    
    def __post_init__(self):
        if self.values is None:
            self.values = deque(maxlen=self.history_size)
    
    def add_value(self, value: float, metadata: dict[str, Any] | None = None):
        """Add new metric value"""
        metric_value = MetricValue(
            timestamp=time.time(),
            value=value,
            unit=self.unit,
            metadata=metadata
        )
        self.values.append(metric_value)
    
    def get_current_value(self) -> float | None:
        """Get most recent metric value"""
        return self.values[-1].value if self.values else None
    
    def get_average(self, duration_seconds: int | None = None) -> float | None:
        """Get average value over specified duration"""
        if not self.values:
            return None
        
        if duration_seconds is None:
            values = [v.value for v in self.values]
        else:
            cutoff_time = time.time() - duration_seconds
            values = [v.value for v in self.values if v.timestamp >= cutoff_time]
        
        return statistics.mean(values) if values else None
    
    def get_max(self, duration_seconds: int | None = None) -> float | None:
        """Get maximum value over specified duration"""
        if not self.values:
            return None
        
        if duration_seconds is None:
            values = [v.value for v in self.values]
        else:
            cutoff_time = time.time() - duration_seconds
            values = [v.value for v in self.values if v.timestamp >= cutoff_time]
        
        return max(values) if values else None
    
    def is_threshold_exceeded(self) -> Tuple[bool, str]:
        """Check if current value exceeds thresholds"""
        current_value = self.get_current_value()
        if current_value is None:
            return False, "no_data"
        
        if self.threshold_critical and current_value >= self.threshold_critical:
            return True, "critical"
        elif self.threshold_warning and current_value >= self.threshold_warning:
            return True, "warning"
        
        return False, "normal"


def _collect_disk_psutil() -> dict[str, float]:
    """Collect disk metrics using psutil"""
    disk_usage = psutil.disk_usage('/')
    disk_io = psutil.disk_io_counters()

    metrics = {
        'disk_usage_percent': (disk_usage.used / disk_usage.total) * 100,
        'disk_total': disk_usage.total,
        'disk_free': disk_usage.free,
        'disk_used': disk_usage.used
    }

    if disk_io:
        metrics.update({
            'disk_read_bytes': disk_io.read_bytes,
            'disk_write_bytes': disk_io.write_bytes,
            'disk_read_count': disk_io.read_count,
            'disk_write_count': disk_io.write_count
        })

    return metrics


def _collect_network_psutil() -> dict[str, float]:
    """Collect network metrics using psutil"""
    network_io = psutil.net_io_counters()
    network_connections = len(psutil.net_connections())

    return {
        'network_bytes_sent': network_io.bytes_sent,
        'network_bytes_recv': network_io.bytes_recv,
        'network_packets_sent': network_io.packets_sent,
        'network_packets_recv': network_io.packets_recv,
        'network_connections_count': network_connections
    }


class SystemMetricsCollector:
    """Collector for system-level performance metrics"""
    
    def __init__(self):
        """Initialize system metrics collector"""
        self.logger = logging.getLogger(__name__)
        self.process = psutil.Process()
        
    def collect_cpu_metrics(self) -> dict[str, float]:
        """Collect CPU usage metrics"""
        try:
            return {
                'cpu_usage_total': psutil.cpu_percent(interval=0.1),
                'cpu_usage_process': self.process.cpu_percent(),
                'cpu_count': psutil.cpu_count(),
                'load_average_1m': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0.0
            }
        except Exception as e:
            self.logger.error(f"Error collecting CPU metrics: {str(e)}")
            return {}
    
    def collect_memory_metrics(self) -> dict[str, float]:
        """Collect memory usage metrics"""
        try:
            return self._collect_memory_psutil()
        except Exception as e:
            self.logger.error(f"Error collecting memory metrics: {str(e)}")
            return {}

    def _collect_memory_psutil(self) -> dict[str, float]:
        """Collect memory metrics using psutil"""
        virtual_memory = psutil.virtual_memory()
        process_memory = self.process.memory_info()
        
        return {
            'memory_usage_percent': virtual_memory.percent,
            'memory_total': virtual_memory.total,
            'memory_available': virtual_memory.available,
            'memory_used': virtual_memory.used,
            'process_memory_rss': process_memory.rss,
            'process_memory_vms': process_memory.vms
        }

    def collect_disk_metrics(self) -> dict[str, float]:
        """Collect disk usage metrics"""
        try:
            return _collect_disk_psutil()
        except Exception as e:
            self.logger.error(f"Error collecting disk metrics: {str(e)}")
            return {}

    def collect_network_metrics(self) -> dict[str, float]:
        """Collect network usage metrics"""
        try:
            return _collect_network_psutil()
        except Exception as e:
            self.logger.error(f"Error collecting network metrics: {str(e)}")
            return {}


class BlockchainMetricsCollector:
    """Collector for blockchain-specific performance metrics"""
    
    def __init__(self):
        """Initialize blockchain metrics collector"""
        self.logger = logging.getLogger(__name__)
        self.event_counts = defaultdict(int)
        self.block_creation_times = deque(maxlen=100)
        self.event_processing_times = deque(maxlen=1000)
        self.consensus_metrics = {
            'rounds': 0,
            'failures': 0,
            'avg_time': 0.0
        }
        
        # Track last collection time for rate calculations
        self.last_collection_time = time.time()
        self.last_event_count = 0
        self.last_block_count = 0
    
    def record_event_processed(self, event_type: str, processing_time: float):
        """Record event processing metrics"""
        self.event_counts[event_type] += 1
        self.event_processing_times.append(processing_time)
    
    def record_block_created(self, creation_time: float, block_size: int):
        """Record block creation metrics"""
        self.block_creation_times.append({
            'time': creation_time,
            'size': block_size,
            'timestamp': time.time()
        })
    
    def record_consensus_round(self, duration: float, success: bool):
        """Record consensus round metrics"""
        self.consensus_metrics['rounds'] += 1
        if not success:
            self.consensus_metrics['failures'] += 1
        
        # Update average time
        total_time = self.consensus_metrics['avg_time'] * (self.consensus_metrics['rounds'] - 1)
        self.consensus_metrics['avg_time'] = (total_time + duration) / self.consensus_metrics['rounds']
    
    def collect_metrics(self) -> dict[str, float]:
        """Collect blockchain performance metrics"""
        try:
            current_time = time.time()
            time_diff = current_time - self.last_collection_time
            
            metrics = {}
            
            # Event processing metrics
            if self.event_processing_times:
                metrics.update({
                    'event_processing_avg_time': statistics.mean(self.event_processing_times),
                    'event_processing_max_time': max(self.event_processing_times),
                    'event_processing_min_time': min(self.event_processing_times)
                })
            
            # Block creation metrics
            if self.block_creation_times:
                recent_blocks = [
                    b for b in self.block_creation_times if current_time - b['timestamp'] <= 300
                ]  # Last 5 minutes
                
                if recent_blocks:
                    creation_times = [b['time'] for b in recent_blocks]
                    block_sizes = [b['size'] for b in recent_blocks]
                    
                    metrics.update({
                        'block_creation_avg_time': statistics.mean(creation_times),
                        'block_creation_rate': len(recent_blocks) / 300.0,  # blocks per second
                        'block_avg_size': statistics.mean(block_sizes)
                    })
            
            # Event throughput
            total_events = sum(self.event_counts.values())
            if time_diff > 0:
                event_rate = (total_events - self.last_event_count) / time_diff
                metrics['event_throughput'] = event_rate
                self.last_event_count = total_events
            
            # Consensus metrics
            metrics.update({
                'consensus_rounds_total': self.consensus_metrics['rounds'],
                'consensus_failures_total': self.consensus_metrics['failures'],
                'consensus_avg_time': self.consensus_metrics['avg_time'],
                'consensus_success_rate': (
                    (self.consensus_metrics['rounds'] - self.consensus_metrics['failures']) / 
                    max(self.consensus_metrics['rounds'], 1)
                ) * 100
            })
            
            self.last_collection_time = current_time
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting blockchain metrics: {str(e)}")
            return {}


def _calculate_report_summary(current_metrics: dict[str, Any]) -> dict[str, int]:
    """Calculate summary counts for the report"""
    return {
        'total_metrics': len(current_metrics),
        'critical_alerts': len([m for m in current_metrics.values() if m['status'] == 'critical']),
        'warning_alerts': len([m for m in current_metrics.values() if m['status'] == 'warning']),
        'normal_metrics': len([m for m in current_metrics.values() if m['status'] == 'normal'])
    }


def _group_metrics_by_type(current_metrics: dict[str, Any]) -> dict[str, list]:
    """Group metrics by their type for reporting"""
    metrics_by_type = defaultdict(list)
    for name, data in current_metrics.items():
        metrics_by_type[data['type']].append((name, data))
    return metrics_by_type


def _get_status_symbol(status: str) -> str:
    """Get the symbol representing a metric status"""
    return {
        'normal': '✓',
        'warning': '⚠',
        'critical': '✗',
        'no_data': '-'
    }.get(status, '?')


def _add_type_section_to_report(lines: list[str], metric_type: str, metrics: list):
    """Add a section for a specific metric type to the text report"""
    lines.append(f"\n{metric_type.upper()} METRICS:")
    lines.append("-" * 30)

    for name, data in metrics:
        status_symbol = _get_status_symbol(data['status'])
        lines.append(f"  {status_symbol} {name}: {data['current_value']} {data['unit']}")

        if data['status'] in ['warning', 'critical']:
            threshold = data.get(f"threshold_{data['status']}")
            if threshold:
                lines.append(f"    ({data['status']} threshold: {threshold})")


def _determine_health_status(avg_score: float, critical_issues: int, warning_issues: int) -> str:
    """Determine health status string based on score and issues"""
    if critical_issues > 0:
        return "critical"
    if warning_issues > 0:
        return "warning"
    if avg_score >= 90:
        return "excellent"
    if avg_score >= 70:
        return "good"
    return "poor"


class PerformanceMonitor:
    """
    Main performance monitoring system for HieraChain framework.
    
    Provides real-time monitoring, alerting, and reporting capabilities
    for system and blockchain performance metrics.
    """
    
    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize performance monitor.
        
        Args:
            config: Monitor configuration parameters
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize collectors
        self.system_collector = SystemMetricsCollector()
        self.blockchain_collector = BlockchainMetricsCollector()
        
        # Metrics registry
        self.metrics: dict[str, PerformanceMetric] = {}
        self._initialize_default_metrics()
        
        # Monitoring configuration
        self.collection_interval = self.config.get('collection_interval', 5.0)  # seconds
        self.enable_alerts = self.config.get('enable_alerts', True)
        self.alert_handlers: list[Callable[[str, PerformanceMetric, float], None]] = []
        
        # Monitoring control
        self.monitoring_active = False
        self.monitoring_thread: threading.Thread | None = None
        self.shutdown_event = threading.Event()
        
        # Custom metrics
        self.custom_metrics_callbacks: dict[str, Callable[[], dict[str, float]]] = {}
    
    def _initialize_default_metrics(self):
        """Initialize default performance metrics"""
        # System metrics
        self.metrics.update({
            'cpu_usage': PerformanceMetric(
                name='cpu_usage',
                metric_type=MetricType.SYSTEM,
                unit=MetricUnit.PERCENTAGE,
                description='CPU usage percentage',
                threshold_warning=80.0,
                threshold_critical=90.0
            ),
            'memory_usage': PerformanceMetric(
                name='memory_usage',
                metric_type=MetricType.SYSTEM,
                unit=MetricUnit.PERCENTAGE,
                description='Memory usage percentage',
                threshold_warning=85.0,
                threshold_critical=95.0
            ),
            'disk_usage': PerformanceMetric(
                name='disk_usage',
                metric_type=MetricType.SYSTEM,
                unit=MetricUnit.PERCENTAGE,
                description='Disk usage percentage',
                threshold_warning=80.0,
                threshold_critical=90.0
            ),
            'network_connections': PerformanceMetric(
                name='network_connections',
                metric_type=MetricType.NETWORK,
                unit=MetricUnit.COUNT,
                description='Number of network connections',
                threshold_warning=1000,
                threshold_critical=2000
            )
        })
        
        # Blockchain metrics
        self.metrics.update({
            'event_throughput': PerformanceMetric(
                name='event_throughput',
                metric_type=MetricType.BLOCKCHAIN,
                unit=MetricUnit.RATE,
                description='Events processed per second',
                threshold_warning=None,  # No warning threshold
                threshold_critical=1.0  # Less than 1 event per second is critical
            ),
            'block_creation_time': PerformanceMetric(
                name='block_creation_time',
                metric_type=MetricType.BLOCKCHAIN,
                unit=MetricUnit.SECONDS,
                description='Average block creation time',
                threshold_warning=30.0,
                threshold_critical=60.0
            ),
            'consensus_success_rate': PerformanceMetric(
                name='consensus_success_rate',
                metric_type=MetricType.CONSENSUS,
                unit=MetricUnit.PERCENTAGE,
                description='Consensus success rate',
                threshold_warning=95.0,
                threshold_critical=90.0
            ),
            'event_processing_time': PerformanceMetric(
                name='event_processing_time',
                metric_type=MetricType.BLOCKCHAIN,
                unit=MetricUnit.SECONDS,
                description='Average event processing time',
                threshold_warning=1.0,
                threshold_critical=5.0
            )
        })
    
    def add_custom_metric(
        self,
        name: str,
        metric_type: MetricType,
        unit: MetricUnit, description: str,
        threshold_warning: float | None = None,
        threshold_critical: float | None = None,
        callback: Callable[[], float] | None = None
    ):
        """Add custom performance metric"""
        self.metrics[name] = PerformanceMetric(
            name=name,
            metric_type=metric_type,
            unit=unit,
            description=description,
            threshold_warning=threshold_warning,
            threshold_critical=threshold_critical
        )
        
        if callback:
            self.custom_metrics_callbacks[name] = lambda: {name: callback()}
        
        self.logger.info(f"Added custom metric: {name}")
    
    def add_alert_handler(self, handler: Callable[[str, PerformanceMetric, float], None]):
        """Add alert handler for threshold violations"""
        self.alert_handlers.append(handler)
    
    def record_blockchain_event(self, event_type: str, processing_time: float):
        """Record blockchain event processing"""
        self.blockchain_collector.record_event_processed(event_type, processing_time)
    
    def record_block_creation(self, creation_time: float, block_size: int):
        """Record block creation"""
        self.blockchain_collector.record_block_created(creation_time, block_size)
    
    def record_consensus_round(self, duration: float, success: bool):
        """Record consensus round"""
        self.blockchain_collector.record_consensus_round(duration, success)
    
    def start_monitoring(self):
        """Start continuous performance monitoring"""
        if self.monitoring_active:
            self.logger.warning("Performance monitoring is already active")
            return
        
        self.monitoring_active = True
        self.shutdown_event.clear()
        
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="PerformanceMonitor"
        )
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        self.logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        self.shutdown_event.set()
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10)
        
        self.logger.info("Performance monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active and not self.shutdown_event.is_set():
            self._execute_monitoring_cycle()
            
            # Wait for next collection interval
            if self.shutdown_event.wait(self.collection_interval):
                break

    def _execute_monitoring_cycle(self):
        """Execute a single monitoring collection and check cycle"""
        try:
            self._collect_all_metrics()
            self._check_thresholds()
        except Exception as cycle_error:
            self.logger.error(f"Error in monitoring cycle: {str(cycle_error)}")

    def _collect_all_metrics(self):
        """Collect all performance metrics"""
        try:
            self._collect_system_metrics()
            self._collect_blockchain_metrics()
            self._collect_custom_metrics()
        except Exception as collect_error:
            self.logger.error(f"Error collecting all metrics: {str(collect_error)}")

    def _collect_system_metrics(self):
        """Collect and map system-level metrics"""
        system_metrics = self.system_collector.collect_cpu_metrics()
        system_metrics.update(self.system_collector.collect_memory_metrics())
        system_metrics.update(self.system_collector.collect_disk_metrics())
        system_metrics.update(self.system_collector.collect_network_metrics())
        
        mapping = {
            'cpu_usage_total': 'cpu_usage',
            'memory_usage_percent': 'memory_usage',
            'disk_usage_percent': 'disk_usage',
            'network_connections_count': 'network_connections'
        }
        self._apply_metric_mapping(system_metrics, mapping)

    def _collect_blockchain_metrics(self):
        """Collect and map blockchain-specific metrics"""
        blockchain_metrics = self.blockchain_collector.collect_metrics()
        
        mapping = {
            'event_throughput': 'event_throughput',
            'block_creation_avg_time': 'block_creation_time',
            'consensus_success_rate': 'consensus_success_rate',
            'event_processing_avg_time': 'event_processing_time'
        }
        self._apply_metric_mapping(blockchain_metrics, mapping)

    def _collect_custom_metrics(self):
        """Collect metrics from custom callbacks"""
        for callback_name, callback in self.custom_metrics_callbacks.items():
            self._process_custom_callback(callback_name, callback)

    def _process_custom_callback(self, callback_name: str, callback: Callable[[], dict[str, float]]):
        """Process a single custom metric callback"""
        try:
            custom_values = callback()
            for metric_name, value in custom_values.items():
                if metric_name in self.metrics:
                    self.metrics[metric_name].add_value(value)
        except Exception as e:
            self.logger.error(f"Error collecting custom metric {callback_name}: {str(e)}")

    def _apply_metric_mapping(self, source_metrics: dict[str, float], mapping: dict[str, str]):
        """Apply a mapping from source keys to our internal metric names"""
        for source_key, internal_name in mapping.items():
            if source_key in source_metrics and internal_name in self.metrics:
                self.metrics[internal_name].add_value(source_metrics[source_key])
    
    def _check_thresholds(self):
        """Check metric thresholds and trigger alerts"""
        if not self.enable_alerts:
            return
        
        for metric_name, metric in self.metrics.items():
            self._process_threshold_check(metric_name, metric)

    def _process_threshold_check(self, metric_name: str, metric: PerformanceMetric):
        """Process threshold check for a single metric"""
        try:
            exceeded, level = metric.is_threshold_exceeded()
            if exceeded and level in ['warning', 'critical']:
                current_value = metric.get_current_value()
                self._trigger_alerts(level, metric, current_value)
                self._log_alert(metric_name, level, metric, current_value)
        except Exception as e:
            self.logger.error(f"Error checking threshold for {metric_name}: {str(e)}")

    def _trigger_alerts(self, level: str, metric: PerformanceMetric, current_value: float):
        """Trigger all registered alert handlers"""
        for handler in self.alert_handlers:
            try:
                handler(level, metric, current_value)
            except Exception as e:
                self.logger.error(f"Alert handler error: {str(e)}")

    def _log_alert(self, metric_name: str, level: str, metric: PerformanceMetric, current_value: float):
        """Log the alert to the system log"""
        threshold = (
            metric.threshold_critical if level == 'critical' else metric.threshold_warning
        )
        self.logger.warning(
            f"Performance alert: {metric_name} = {current_value} "
            f"({level} threshold: {threshold})"
        )
    
    def get_current_metrics(self) -> dict[str, dict[str, Any]]:
        """Get current metric values and statistics"""
        result = {}
        
        for name, metric in self.metrics.items():
            current_value = metric.get_current_value()
            
            result[name] = {
                'current_value': current_value,
                'unit': metric.unit.value,
                'description': metric.description,
                'type': metric.metric_type.value,
                'threshold_warning': metric.threshold_warning,
                'threshold_critical': metric.threshold_critical,
                'avg_5min': metric.get_average(300),  # 5 minutes
                'avg_1hour': metric.get_average(3600),  # 1 hour
                'max_5min': metric.get_max(300),
                'data_points': len(metric.values) if metric.values else 0,
                'status': metric.is_threshold_exceeded()[1]
            }
        
        return result
    
    def get_metric_history(
        self,
        metric_name: str,
        duration_seconds: int | None = None
    ) -> list[dict[str, Any]]:
        """Get metric value history"""
        if metric_name not in self.metrics:
            return []
        
        metric = self.metrics[metric_name]
        
        if duration_seconds is None:
            values = list(metric.values)
        else:
            cutoff_time = time.time() - duration_seconds
            values = [v for v in metric.values if v.timestamp >= cutoff_time]
        
        return [asdict(v) for v in values]
    
    def generate_report(self, format_type: str = "json") -> str:
        """Generate performance report"""
        current_metrics = self.get_current_metrics()
        
        if format_type.lower() == "json":
            return self._generate_json_report(current_metrics)
        elif format_type.lower() == "text":
            return self._generate_text_report(current_metrics)
        else:
            raise ValueError(f"Unsupported report format: {format_type}")

    def _generate_json_report(self, current_metrics: dict[str, Any]) -> str:
        """Generate JSON format report"""
        report_data = {
            'timestamp': time.time(),
            'monitoring_status': 'active' if self.monitoring_active else 'inactive',
            'metrics': current_metrics,
            'summary': _calculate_report_summary(current_metrics)
        }
        return json.dumps(report_data, indent=2, default=str)

    def _generate_text_report(self, current_metrics: dict[str, Any]) -> str:
        """Generate human-readable text report"""
        lines = [
            "Performance Monitoring Report",
            "=" * 50,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Status: {'Active' if self.monitoring_active else 'Inactive'}",
            ""
        ]
        
        metrics_by_type = _group_metrics_by_type(current_metrics)
        for metric_type, metrics in metrics_by_type.items():
            _add_type_section_to_report(lines, metric_type, metrics)
            
        return "\n".join(lines)

    def get_health_score(self) -> Tuple[float, str]:
        """Calculate overall system health score (0-100)"""
        if not self.metrics:
            return 0.0, "no_data"
        
        scores, critical_issues, warning_issues = self._calculate_issue_counts()
        
        if not scores:
            return 0.0, "no_data"
        
        avg_score = statistics.mean(scores)
        status = _determine_health_status(avg_score, critical_issues, warning_issues)
        
        return avg_score, status

    def _calculate_issue_counts(self) -> Tuple[list[float], int, int]:
        """Calculate scores and issue counts for health assessment"""
        scores = []
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
                
        return scores, critical_issues, warning_issues


def create_default_alert_handler() -> Callable[[str, PerformanceMetric, float], None]:
    """Create default alert handler that logs alerts"""
    def alert_handler(level: str, metric: PerformanceMetric, value: float):
        logger = logging.getLogger("PerformanceMonitor.Alerts")
        logger.warning(
            f"PERFORMANCE ALERT: {metric.name} = {value} {metric.unit.value} "
            f"(threshold: {getattr(metric, f'threshold_{level}', 'unknown')}) "
            f"- {metric.description}"
        )
    
    return alert_handler
