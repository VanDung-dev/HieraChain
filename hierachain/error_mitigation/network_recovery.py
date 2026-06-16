"""
Network recovery engine for HieraChain Ledger.
"""

import time
import json
import logging
import asyncio
import os
from typing import Any
from datetime import datetime

from hierachain.error_mitigation.recovery_types import RecoveryError

logger = logging.getLogger(__name__)


class NetworkRecoveryEngine:
    def __init__(self, consensus_config: dict[str, Any]):
        self.config = consensus_config
        self.timeout_base = 5.0
        self.timeout_multiplier = self.config.get("timeout_multiplier", 2.0)
        self.redundancy_factor = self.config.get("redundancy_factor", 2)
        self.max_retries = self.config.get("max_retries", 3)
        self.latency_history = []
        self.network_health = {}
        self.partition_detected = False

        logger.info(
            "Initialized NetworkRecoveryEngine with redundancy_factor=%d",
            self.redundancy_factor
        )

    def adjust_timeout(self, latency_history_input: list[float]) -> float:
        if not latency_history_input:
            return self.timeout_base * self.timeout_multiplier
        avg_latency = sum(latency_history_input) / len(latency_history_input)
        max_latency = max(latency_history_input)
        network_factor = 1 + (avg_latency / 1000)
        volatility_factor = 1 + (max_latency - avg_latency) / 1000
        calculated_timeout = (
            self.timeout_base * network_factor * volatility_factor * self.timeout_multiplier
        )
        max_timeout = self.config.get("max_timeout", 30.0)
        calculated_timeout = min(calculated_timeout, max_timeout)
        logger.info(
            "Timeout adjusted to %.2f s based on avg latency %.1f ms",
            calculated_timeout, avg_latency
        )
        return calculated_timeout

    async def send_with_redundancy(
        self, message: dict[str, Any], target_nodes: list[str]
    ) -> dict[str, Any]:
        if not target_nodes:
            raise RecoveryError("No target nodes provided for redundant sending")

        futures = []
        for path_id in range(min(self.redundancy_factor, len(target_nodes))):
            target_node = target_nodes[path_id % len(target_nodes)]
            future = asyncio.create_task(
                self._send_via_path(message, target_node, path_id)
            )
            futures.append(future)

        try:
            done, pending = await asyncio.wait(
                futures, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                if not task.exception():
                    result = await task
                    logger.info("Message sent successfully via redundant path")
                    return result
            raise RecoveryError("All redundant paths failed")
        except asyncio.TimeoutError:
            raise RecoveryError("Network timeout on all paths")

    async def _send_via_path(
        self, message: dict[str, Any], target_node: str, path_id: int
    ) -> dict[str, Any]:
        _ = message
        start_time = time.time()
        try:
            await asyncio.sleep(0.1)
            latency = (time.time() - start_time) * 1000
            self.latency_history.append(latency)
            if len(self.latency_history) > 100:
                self.latency_history = self.latency_history[-50:]
            response = {
                "status": "success",
                "target_node": target_node,
                "path_id": path_id,
                "latency_ms": latency,
                "timestamp": time.time(),
                "message_content": str(message)
            }
            logger.debug(
                "Message sent via path %d to %s (latency: %.1f ms)",
                path_id, target_node, latency
            )
            return response
        except Exception as e:
            logger.error("Path %d to %s failed: %s", path_id, target_node, str(e))
            raise RecoveryError(f"Path {path_id} failed: {str(e)}")

    def monitor_network_health(self) -> dict[str, Any]:
        health_status = {
            "timestamp": time.time(),
            "avg_latency_ms": 0,
            "max_latency_ms": 0,
            "partition_detected": False,
            "healthy_paths": 0,
            "total_paths": self.redundancy_factor
        }
        if self.latency_history:
            health_status["avg_latency_ms"] = (
                sum(self.latency_history) / len(self.latency_history)
            )
            health_status["max_latency_ms"] = max(self.latency_history)
        if health_status["avg_latency_ms"] > 5000:
            self.partition_detected = True
            health_status["partition_detected"] = True
            logger.warning("Network partition detected based on high latency")
            self._initiate_view_change()
        return health_status

    def _initiate_view_change(self) -> None:
        view_change_event = {
            "event": "view_change_initiated",
            "reason": "network_partition",
            "timestamp": time.time(),
            "network_health": {
                "partition_detected": self.partition_detected,
                "avg_latency_ms": sum(self.latency_history) / max(len(self.latency_history), 1)
            }
        }
        logger.info("View change initiated: %s", json.dumps(view_change_event))
        self._send_alert("Network partition detected, view change initiated")

    @staticmethod
    def _send_alert(message: str) -> None:
        alert = {
            "event": "network_alert",
            "message": message,
            "timestamp": time.time(),
            "severity": "high"
        }
        logger.warning("Network alert: %s", message)
        try:
            os.makedirs("log/error_mitigation", exist_ok=True)
            with open("log/error_mitigation/network_alerts.log", "a") as f:
                f.write(f"{datetime.now().isoformat()}: {json.dumps(alert)}\n")
        except Exception as e:
            logger.error("Failed to write network alert: %s", str(e))
