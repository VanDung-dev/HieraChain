"""
Resource validator for HieraChain Ledger.

Validates system resource usage and thresholds.
"""

from __future__ import annotations

import orjson
import time
import logging
from typing import Any, cast

logger = logging.getLogger(__name__)


class ResourceValidator:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.cpu_threshold = config.get("cpu_threshold", 70)
        self.memory_threshold = config.get("memory_threshold", 80)
        self.disk_threshold = config.get("disk_threshold", 85)
        self.auto_scale = config.get("auto_scale", False)
        logger.info("Initialized ResourceValidator")

    def validate_resources(self) -> dict[str, Any]:
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            resource_status = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": (disk.used / disk.total) * 100,
                "timestamp": time.time(),
                "violations": [],
            }
            self._check_cpu_usage(cpu_percent, resource_status)
            self._check_memory_usage(memory.percent, resource_status)
            self._check_disk_usage(cast(float, resource_status["disk_percent"]), resource_status)
            if not resource_status["violations"]:
                logger.info("All resource thresholds within limits")
            return resource_status
        except ImportError:
            logger.error("psutil not available for resource monitoring")
            return {"error": "Resource monitoring unavailable", "violations": []}
        except Exception as ex:
            logger.error("Resource validation failed: %s", ex)
            return {"error": str(ex), "violations": []}

    def _check_cpu_usage(self, cpu_percent: float, status: dict[str, Any]) -> None:
        if cpu_percent > self.cpu_threshold:
            violation = f"CPU usage {cpu_percent:.1f}% > {self.cpu_threshold}%"
            status["violations"].append(violation)
            logger.warning(violation)
            if self.auto_scale:
                self._trigger_scaling("cpu")

    def _check_memory_usage(self, memory_percent: float, status: dict[str, Any]) -> None:
        if memory_percent > self.memory_threshold:
            violation = f"Memory usage {memory_percent:.1f}% > {self.memory_threshold}%"
            status["violations"].append(violation)
            logger.warning(violation)
            if self.auto_scale:
                self._trigger_scaling("memory")

    def _check_disk_usage(self, disk_percent: float, status: dict[str, Any]) -> None:
        if disk_percent > self.disk_threshold:
            violation = f"Disk usage {disk_percent:.1f}% > {self.disk_threshold}%"
            status["violations"].append(violation)
            logger.warning(violation)

    def _trigger_scaling(self, resource_type: str) -> None:
        scaling_event = {
            "event": "resource_scaling_triggered",
            "resource_type": resource_type,
            "timestamp": time.time(),
            "auto_scale_enabled": self.auto_scale,
        }
        logger.info("Resource scaling triggered: %s", orjson.dumps(scaling_event).decode())
        from hierachain.core.parquet_log import write_parquet_log
        write_parquet_log("log/error_mitigation/resource_scaling.parquet", scaling_event)
