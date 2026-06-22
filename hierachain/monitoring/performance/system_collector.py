"""
System metrics collector utilizing psutil for HieraChain Ledger.
"""

from __future__ import annotations

import logging
import psutil


class SystemMetricsCollector:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.process = psutil.Process()

    def collect_cpu_metrics(self) -> dict[str, float]:
        try:
            cpu_count = psutil.cpu_count()
            return {
                'cpu_usage_total': float(psutil.cpu_percent(interval=0.1)),
                'cpu_usage_process': float(self.process.cpu_percent()),
                'cpu_count': float(cpu_count if cpu_count is not None else 0),
                'load_average_1m': float(
                    psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0.0
                )
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
        'memory_usage_percent': float(virtual_memory.percent),
        'memory_total': float(virtual_memory.total),
        'memory_available': float(virtual_memory.available),
        'memory_used': float(virtual_memory.used),
        'process_memory_rss': float(process_memory.rss),
        'process_memory_vms': float(process_memory.vms)
    }


def _collect_disk_psutil() -> dict[str, float]:
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
            'disk_read_bytes': float(disk_io.read_bytes),
            'disk_write_bytes': float(disk_io.write_bytes),
            'disk_read_count': float(disk_io.read_count),
            'disk_write_count': float(disk_io.write_count)
        })
    return metrics


def _collect_network_psutil() -> dict[str, float]:
    network_io = psutil.net_io_counters()
    network_connections = len(psutil.net_connections())
    return {
        'network_bytes_sent': float(network_io.bytes_sent),
        'network_bytes_recv': float(network_io.bytes_recv),
        'network_packets_sent': float(network_io.packets_sent),
        'network_packets_recv': float(network_io.packets_recv),
        'network_connections_count': float(network_connections)
    }
