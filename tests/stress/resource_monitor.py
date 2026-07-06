"""
Container Resource Monitor.
Collects granular CPU and memory consumption statistics from running Docker containers.
# ponytail: simple direct docker client integration for metric collection
"""

import time
import logging
import docker
from typing import Dict, Any, Optional

class ResourceMonitor:
    def __init__(self, container_name: str):
        self.container_name = container_name
        self.docker_client = docker.from_env()
        self.container = self.docker_client.containers.get(container_name)
        self.logger = logging.getLogger(__name__)
        self.stop_monitoring = False

    def start_monitoring(self, interval: float = 1.0) -> None:
        """Bắt đầu giám sát tài nguyên với khoảng cách thời gian được chỉ định."""
        self.stop_monitoring = False
        try:
            while not self.stop_monitoring:
                metrics = self.get_current_metrics()
                self.log_metrics(metrics)
                time.sleep(interval)
        except Exception as e:
            self.logger.error(f"Error during monitoring: {e}")

    def stop_monitoring(self) -> None:
        """Dừng việc giám sát tài nguyên."""
        self.stop_monitoring = True

    def get_current_metrics(self) -> Dict[str, Any]:
        """Lấy các chỉ số tài nguyên hiện tại."""
        try:
            # Lấy thông tin CPU
            cpu_percent = self.container.stats(stream=False)[0]["cpu_stats"]["cpu_usage"]["total_usage"]
            
            # Lấy thông tin RAM
            mem_stats = self.container.stats(stream=False)[0]["memory_stats"]
            mem_usage = mem_stats["usage"]
            mem_limit = mem_stats["limit"]
            
            # Lấy thông tin mạng
            net_stats = self.container.stats(stream=False)[0]["networks"]
            net_rx = sum([stats["rx_bytes"] for stats in net_stats.values()])
            net_tx = sum([stats["tx_bytes"] for stats in net_stats.values()])
            
            # Lấy thông tin I/O
            io_stats = self.container.stats(stream=False)[0]["blkio_stats"]
            io_read = sum([stats["value"] for stats in io_stats if stats["op"] == "read"])
            io_write = sum([stats["value"] for stats in io_stats if stats["op"] == "write"])
            
            return {
                "cpu_percent": cpu_percent,
                "mem_usage": mem_usage,
                "mem_limit": mem_limit,
                "mem_percent": (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0,
                "net_rx": net_rx,
                "net_tx": net_tx,
                "io_read": io_read,
                "io_write": io_write,
                "timestamp": time.time()
            }
        except Exception as e:
            self.logger.error(f"Error getting metrics: {e}")
            return {}

    def log_metrics(self, metrics: Dict[str, Any]) -> None:
        """Ghi log các chỉ số tài nguyên."""
        if not metrics:
            return
        
        self.logger.info(
            f"[{self.container_name}] "
            f"CPU: {metrics['cpu_percent']}%, "
            f"Memory: {metrics['mem_usage']}/{metrics['mem_limit']} ({metrics['mem_percent']:.2f}%), "
            f"Network: RX {metrics['net_rx']} / TX {metrics['net_tx']}, "
            f"I/O: Read {metrics['io_read']} / Write {metrics['io_write']}, "
            f"Timestamp: {metrics['timestamp']}"
        )

    def get_container_stats(self) -> Optional[Dict[str, Any]]:
        """Lấy thông tin thống kê của container."""
        try:
            return self.container.stats(stream=False)
        except Exception as e:
            self.logger.error(f"Error getting container stats: {e}")
            return None

# Example usage
if __name__ == "__main__":
    monitor = ResourceMonitor("my_container")
    monitor.start_monitoring(interval=5)
    time.sleep(30)  # Giám sát trong 30 giây
    monitor.stop_monitoring()