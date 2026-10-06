"""
Resource validator for HieraChain Ledger.

Validates system resource usage and thresholds.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from hierachain.serialization import dumps_json

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
        """Report resource violations; legacy auto_scale enables logged advice only."""
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
            for resource_type, label, percent, threshold in (
                ("cpu", "CPU", cpu_percent, self.cpu_threshold),
                ("memory", "Memory", memory.percent, self.memory_threshold),
                ("disk", "Disk", resource_status["disk_percent"], self.disk_threshold),
            ):
                if percent > threshold:
                    violation = f"{label} usage {percent:.1f}% > {threshold}%"
                    resource_status["violations"].append(violation)
                    logger.warning(violation)
                    if self.auto_scale and resource_type != "disk":
                        self._log_capacity_recommendation(resource_type)
            if not resource_status["violations"]:
                logger.info("All resource thresholds within limits")
            return resource_status
        except ImportError:
            logger.error("psutil not available for resource monitoring")
            return {"error": "Resource monitoring unavailable", "violations": []}
        except Exception as ex:
            logger.error("Resource validation failed: %s", ex)
            return {"error": str(ex), "violations": []}

    def _log_capacity_recommendation(self, resource_type: str) -> None:
        recommendation = {
            "event": "resource_capacity_recommendation",
            "resource_type": resource_type,
            "timestamp": time.time(),
            "auto_scale_enabled": self.auto_scale,
        }
        logger.info("Resource capacity recommendation for the host application: %s", dumps_json(recommendation))
        from hierachain.core.parquet_log import write_parquet_log
        write_parquet_log("log/error_mitigation/resource_scaling.parquet", recommendation)
