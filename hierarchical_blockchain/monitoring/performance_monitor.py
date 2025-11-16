"""
Performance Monitoring Module for Hierarchical Blockchain Framework

This module provides comprehensive real-time performance monitoring capabilities
for tracking system health, resource usage, and performance metrics. Supports
CPU, memory, throughput, and custom metrics.
"""

import time
import threading
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque, defaultdict
import statistics
import json
import os
from datetime import datetime

# Optional dependency - graceful degradation if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


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
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PerformanceMetric:
    """Performance metric definition and history"""
    name: str
    metric_type: MetricType
    unit: MetricUnit
    description: str
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    history_size: int = 1000
    values: Optional[deque] = None
    
    def __post_init__(self):
        if self.values is None:
            self.values = deque(maxlen=self.history_size)
    
    def add_value(self, value: float, metadata: Optional[Dict[str, Any]] = None):
        """Add new metric value"""
        metric_value = MetricValue(
            timestamp=time.time(),
            value=value,
            unit=self.unit,
            metadata=metadata
        )
        self.values.append(metric_value)
    
    def get_current_value(self) -> Optional[float]:
        """Get most recent metric value"""
        return self.values[-1].value if self.values else None
    
    def get_average(self, duration_seconds: Optional[int] = None) -> Optional[float]:
        """Get average value over specified duration"""
        if not self.values:
            return None
        
        if duration_seconds is None:
            values = [v.value for v in self.values]
        else:
            cutoff_time = time.time() - duration_seconds
            values = [v.value for v in self.values if v.timestamp >= cutoff_time]
        
        return statistics.mean(values) if values else None
    
    def get_max(self, duration_seconds: Optional[int] = None) -> Optional[float]:
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


class SystemMetricsCollector:
    """Collector for system-level performance metrics"""
    
    def __init__(self):
        """Initialize system metrics collector"""
        self.logger = logging.getLogger(__name__)
        self.process = psutil.Process() if PSUTIL_AVAILABLE else None
        
        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil not available - using fallback system metrics collection")
        
    def collect_cpu_metrics(self) -> Dict[str, float]:
        """Collect CPU usage metrics"""
        try:
            if PSUTIL_AVAILABLE:
                return {
                    'cpu_usage_total': psutil.cpu_percent(interval=0.1),
                    'cpu_usage_process': self.process.cpu_percent(),
                    'cpu_count': psutil.cpu_count(),
                    'load_average_1m': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0.0
                }
            else:
                # Fallback implementation
                cpu_count = os.cpu_count() or 1
                
                # Try to get load average on Unix-like systems
                load_avg = 0.0
                try:
                    if hasattr(os, 'getloadavg'):
                        load_avg = os.getloadavg()[0]
                    elif os.path.exists('/proc/loadavg'):
                        with open('/proc/loadavg', 'r') as load_file:
                            load_avg = float(load_file.read().split()[0])
                except (IOError, OSError):
                    pass
                
                return {
                    'cpu_usage_total': min(load_avg * 100 / cpu_count, 100.0),  # Rough approximation
                    'cpu_usage_process': 0.0,  # Cannot determine without psutil
                    'cpu_count': cpu_count,
                    'load_average_1m': load_avg
                }
        except Exception as e:
            self.logger.error(f"Error collecting CPU metrics: {str(e)}")
            return {}
    
    def collect_memory_metrics(self) -> Dict[str, float]:
        """Collect memory usage metrics"""
        try:
            if PSUTIL_AVAILABLE:
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
            else:
                # Fallback implementation using /proc/meminfo on Linux
                memory_info = {}
                try:
                    if os.path.exists('/proc/meminfo'):
                        with open('/proc/meminfo', 'r') as mem_file:
                            for line in mem_file:
                                if ':' in line:
                                    key, value = line.split(':', 1)
                                    memory_info[key.strip()] = int(value.strip().split()[0]) * 1024  # Convert KB to bytes
                    
                    total = memory_info.get('MemTotal', 0)
                    available = memory_info.get('MemAvailable', memory_info.get('MemFree', 0))
                    used = total - available
                    usage_percent = (used / total * 100) if total > 0 else 0
                    
                    return {
                        'memory_usage_percent': usage_percent,
                        'memory_total': total,
                        'memory_available': available,
                        'memory_used': used,
                        'process_memory_rss': 0,  # Cannot determine without psutil
                        'process_memory_vms': 0   # Cannot determine without psutil
                    }
                except (IOError, OSError, ValueError):
                    return {
                        'memory_usage_percent': 0,
                        'memory_total': 0,
                        'memory_available': 0,
                        'memory_used': 0,
                        'process_memory_rss': 0,
                        'process_memory_vms': 0
                    }
        except Exception as e:
            self.logger.error(f"Error collecting memory metrics: {str(e)}")
            return {}
    
    def collect_disk_metrics(self) -> Dict[str, float]:
        """Collect disk usage metrics"""
        try:
            if PSUTIL_AVAILABLE:
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
            else:
                # Fallback implementation using os.statvfs and /proc/diskstats
                metrics = {}
                try:
                    # Get disk usage using statvfs
                    if hasattr(os, 'statvfs'):
                        statvfs = os.statvfs('/')
                        total = statvfs.f_frsize * statvfs.f_blocks
                        free = statvfs.f_frsize * statvfs.f_bavail
                        used = total - free
                        usage_percent = (used / total * 100) if total > 0 else 0
                        
                        metrics.update({
                            'disk_usage_percent': usage_percent,
                            'disk_total': total,
                            'disk_free': free,
                            'disk_used': used
                        })
                    
                    # Try to get disk I/O stats from /proc/diskstats (Linux only)
                    if os.path.exists('/proc/diskstats'):
                        with open('/proc/diskstats', 'r') as disk_file:
                            total_read_bytes = 0
                            total_write_bytes = 0
                            for line in disk_file:
                                fields = line.split()
                                if len(fields) >= 10:
                                    # Fields: read_sectors, write_sectors (sectors are typically 512 bytes)
                                    read_sectors = int(fields[5])
                                    write_sectors = int(fields[9])
                                    total_read_bytes += read_sectors * 512
                                    total_write_bytes += write_sectors * 512
                            
                            metrics.update({
                                'disk_read_bytes': total_read_bytes,
                                'disk_write_bytes': total_write_bytes,
                                'disk_read_count': 0,  # Not available in fallback
                                'disk_write_count': 0  # Not available in fallback
                            })
                    
                    return metrics
                except (IOError, OSError, ValueError):
                    return {
                        'disk_usage_percent': 0,
                        'disk_total': 0,
                        'disk_free': 0,
                        'disk_used': 0,
                        'disk_read_bytes': 0,
                        'disk_write_bytes': 0,
                        'disk_read_count': 0,
                        'disk_write_count': 0
                    }
        except Exception as e:
            self.logger.error(f"Error collecting disk metrics: {str(e)}")
            return {}
    
    def collect_network_metrics(self) -> Dict[str, float]:
        """Collect network usage metrics"""
        try:
            if PSUTIL_AVAILABLE:
                network_io = psutil.net_io_counters()
                network_connections = len(psutil.net_connections())
                
                return {
                    'network_bytes_sent': network_io.bytes_sent,
                    'network_bytes_recv': network_io.bytes_recv,
                    'network_packets_sent': network_io.packets_sent,
                    'network_packets_recv': network_io.packets_recv,
                    'network_connections_count': network_connections
                }
            else:
                # Fallback implementation using /proc/net/dev and /proc/net/tcp
                metrics = {
                    'network_bytes_sent': 0,
                    'network_bytes_recv': 0,
                    'network_packets_sent': 0,
                    'network_packets_recv': 0,
                    'network_connections_count': 0
                }
                
                try:
                    # Get network I/O stats from /proc/net/dev (Linux)
                    if os.path.exists('/proc/net/dev'):
                        with open('/proc/net/dev', 'r') as net_file:
                            lines = net_file.readlines()[2:]  # Skip header lines
                            for line in lines:
                                if ':' in line:
                                    fields = line.split()
                                    if len(fields) >= 10:
                                        # Received bytes and packets
                                        metrics['network_bytes_recv'] += int(fields[1])
                                        metrics['network_packets_recv'] += int(fields[2])
                                        # Transmitted bytes and packets
                                        metrics['network_bytes_sent'] += int(fields[9])
                                        metrics['network_packets_sent'] += int(fields[10])
                    
                    # Count network connections from /proc/net/tcp and /proc/net/udp (Linux)
                    connection_count = 0
                    for protocol in ['tcp', 'udp', 'tcp6', 'udp6']:
                        proc_file = f'/proc/net/{protocol}'
                        if os.path.exists(proc_file):
                            with open(proc_file, 'r') as conn_file:
                                lines = conn_file.readlines()[1:]  # Skip header
                                connection_count += len(lines)
                    
                    metrics['network_connections_count'] = connection_count
                    
                except (IOError, OSError):
                    pass  # Keep default values
                
                return metrics
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
    
    def collect_metrics(self) -> Dict[str, float]:
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
                recent_blocks = [b for b in self.block_creation_times 
                               if current_time - b['timestamp'] <= 300]  # Last 5 minutes
                
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


class PerformanceMonitor:
    """
    Main performance monitoring system for hierarchical blockchain framework.
    
    Provides real-time monitoring, alerting, and reporting capabilities
    for system and blockchain performance metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
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
        self.metrics: Dict[str, PerformanceMetric] = {}
        self._initialize_default_metrics()
        
        # Monitoring configuration
        self.collection_interval = self.config.get('collection_interval', 5.0)  # seconds
        self.enable_alerts = self.config.get('enable_alerts', True)
        self.alert_handlers: List[Callable[[str, PerformanceMetric, float], None]] = []
        
        # Monitoring control
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Custom metrics
        self.custom_metrics_callbacks: Dict[str, Callable[[], Dict[str, float]]] = {}
    
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
    
    def add_custom_metric(self, name: str, metric_type: MetricType, 
                         unit: MetricUnit, description: str,
                         threshold_warning: Optional[float] = None,
                         threshold_critical: Optional[float] = None,
                         callback: Optional[Callable[[], float]] = None):
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
            try:
                self._collect_all_metrics()
                self._check_thresholds()
            except Exception as loop_error:
                self.logger.error(f"Error in monitoring loop: {str(loop_error)}")
            
            # Wait for next collection interval
            if not self.shutdown_event.wait(self.collection_interval):
                continue
            else:
                break
    
    def _collect_all_metrics(self):
        """Collect all performance metrics"""
        try:
            # Collect system metrics
            system_metrics = self.system_collector.collect_cpu_metrics()
            system_metrics.update(self.system_collector.collect_memory_metrics())
            system_metrics.update(self.system_collector.collect_disk_metrics())
            system_metrics.update(self.system_collector.collect_network_metrics())
            
            # Map system metrics to our metric objects
            metric_mapping = {
                'cpu_usage_total': 'cpu_usage',
                'memory_usage_percent': 'memory_usage',
                'disk_usage_percent': 'disk_usage',
                'network_connections_count': 'network_connections'
            }
            
            for sys_metric, our_metric in metric_mapping.items():
                if sys_metric in system_metrics and our_metric in self.metrics:
                    self.metrics[our_metric].add_value(system_metrics[sys_metric])
            
            # Collect blockchain metrics
            blockchain_metrics = self.blockchain_collector.collect_metrics()
            
            blockchain_mapping = {
                'event_throughput': 'event_throughput',
                'block_creation_avg_time': 'block_creation_time',
                'consensus_success_rate': 'consensus_success_rate',
                'event_processing_avg_time': 'event_processing_time'
            }
            
            for bc_metric, our_metric in blockchain_mapping.items():
                if bc_metric in blockchain_metrics and our_metric in self.metrics:
                    self.metrics[our_metric].add_value(blockchain_metrics[bc_metric])
            
            # Collect custom metrics
            for callback_name, callback in self.custom_metrics_callbacks.items():
                try:
                    custom_values = callback()
                    for metric_name, value in custom_values.items():
                        if metric_name in self.metrics:
                            self.metrics[metric_name].add_value(value)
                except Exception as callback_error:
                    self.logger.error(f"Error collecting custom metric {callback_name}: {str(callback_error)}")
            
        except Exception as collect_error:
            self.logger.error(f"Error collecting metrics: {str(collect_error)}")
    
    def _check_thresholds(self):
        """Check metric thresholds and trigger alerts"""
        if not self.enable_alerts:
            return
        
        for metric_name, metric in self.metrics.items():
            try:
                exceeded, level = metric.is_threshold_exceeded()
                
                if exceeded and level in ['warning', 'critical']:
                    current_value = metric.get_current_value()
                    
                    # Trigger alert handlers
                    for handler in self.alert_handlers:
                        try:
                            handler(level, metric, current_value)
                        except Exception as handler_error:
                            self.logger.error(f"Alert handler error: {str(handler_error)}")
                    
                    # Log the alert
                    threshold = (metric.threshold_critical if level == 'critical' 
                               else metric.threshold_warning)
                    self.logger.warning(
                        f"Performance alert: {metric_name} = {current_value} "
                        f"({level} threshold: {threshold})"
                    )
                    
            except Exception as check_error:
                self.logger.error(f"Error checking threshold for {metric_name}: {str(check_error)}")
    
    def get_current_metrics(self) -> Dict[str, Dict[str, Any]]:
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
    
    def get_metric_history(self, metric_name: str, 
                          duration_seconds: Optional[int] = None) -> List[Dict[str, Any]]:
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
            report_data = {
                'timestamp': time.time(),
                'monitoring_status': 'active' if self.monitoring_active else 'inactive',
                'metrics': current_metrics,
                'summary': {
                    'total_metrics': len(current_metrics),
                    'critical_alerts': len([m for m in current_metrics.values() if m['status'] == 'critical']),
                    'warning_alerts': len([m for m in current_metrics.values() if m['status'] == 'warning']),
                    'normal_metrics': len([m for m in current_metrics.values() if m['status'] == 'normal'])
                }
            }
            
            return json.dumps(report_data, indent=2, default=str)
        
        elif format_type.lower() == "text":
            lines = [
                "Performance Monitoring Report",
                "=" * 50,
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Status: {'Active' if self.monitoring_active else 'Inactive'}",
                ""
            ]
            
            # Group metrics by type
            metrics_by_type = defaultdict(list)
            for name, data in current_metrics.items():
                metrics_by_type[data['type']].append((name, data))
            
            for metric_type, metrics in metrics_by_type.items():
                lines.append(f"\n{metric_type.upper()} METRICS:")
                lines.append("-" * 30)
                
                for name, data in metrics:
                    status_symbol = {
                        'normal': '✓',
                        'warning': '⚠',
                        'critical': '✗',
                        'no_data': '-'
                    }.get(data['status'], '?')
                    
                    lines.append(f"  {status_symbol} {name}: {data['current_value']} {data['unit']}")
                    if data['status'] in ['warning', 'critical']:
                        threshold_key = f"threshold_{data['status']}"
                        threshold = data.get(threshold_key)
                        if threshold:
                            lines.append(f"    ({data['status']} threshold: {threshold})")
            
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported report format: {format_type}")
    
    def get_health_score(self) -> Tuple[float, str]:
        """Calculate overall system health score (0-100)"""
        if not self.metrics:
            return 0.0, "no_data"
        
        scores = []
        critical_issues = 0
        warning_issues = 0
        
        for metric in self.metrics.values():
            exceeded, level = metric.is_threshold_exceeded()
            
            if level == "critical":
                scores.append(0.0)
                critical_issues += 1
            elif level == "warning":
                scores.append(50.0)
                warning_issues += 1
            elif level == "normal":
                scores.append(100.0)
            # Skip "no_data" metrics
        
        if not scores:
            return 0.0, "no_data"
        
        avg_score = statistics.mean(scores)
        
        if critical_issues > 0:
            status = "critical"
        elif warning_issues > 0:
            status = "warning"
        elif avg_score >= 90:
            status = "excellent"
        elif avg_score >= 70:
            status = "good"
        else:
            status = "poor"
        
        return avg_score, status


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


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Monitor")
    parser.add_argument("--duration", type=int, default=60, help="Monitoring duration in seconds")
    parser.add_argument("--interval", type=float, default=5.0, help="Collection interval in seconds")
    parser.add_argument("--output", help="Output file for report")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create and configure monitor
    monitor_config = {
        'collection_interval': args.interval,
        'enable_alerts': True
    }
    
    monitor = PerformanceMonitor(monitor_config)
    monitor.add_alert_handler(create_default_alert_handler())
    
    # Start monitoring
    monitor.start_monitoring()
    
    try:
        print(f"Monitoring for {args.duration} seconds...")
        time.sleep(args.duration)
        
        # Generate report
        report = monitor.generate_report("text")
        
        if args.output:
            with open(args.output, 'w') as report_file:
                report_file.write(report)
            print(f"Report saved to {args.output}")
        else:
            print("\n" + report)
        
        # Print health score
        health_score, health_status = monitor.get_health_score()
        print(f"\nOverall Health Score: {health_score:.1f}/100 ({health_status})")
        
    except KeyboardInterrupt:
        print("\nMonitoring interrupted by user")
    finally:
        monitor.stop_monitoring()