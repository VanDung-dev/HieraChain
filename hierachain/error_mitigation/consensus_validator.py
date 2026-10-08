"""
Consensus validator for HieraChain Ledger.

Validates BFT consensus requirements including node count and health.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from hierachain.error_mitigation.validator_exceptions import ValidationError
from hierachain.error_mitigation.validator_helpers import _log_capacity_recommendation

logger = logging.getLogger(__name__)


class ConsensusValidator:
    def __init__(self, consensus_config: dict[str, Any]) -> None:
        self.config = consensus_config
        self.f = self.config.get("f", 1)
        self.auto_scale_threshold = self.config.get("auto_scale_threshold", 0.8)
        self.health_check_interval = self.config.get("health_check_interval", 30)
        logger.info("Initialized ConsensusValidator with f=%d", self.f)

    def validate_node_count(self, current_nodes: list[Any]) -> bool:
        required_nodes = 3 * self.f + 1
        actual_nodes = len(current_nodes)
        if actual_nodes < required_nodes:
            logger.error(
                "Insufficient nodes for BFT consensus: %d < %d. For f=%d faulty nodes tolerance, "
                "need at least %d nodes. Capacity must be restored by the host application.",
                actual_nodes, required_nodes, self.f, required_nodes,
            )
            raise ValidationError("insufficient_nodes")
        logger.info("Node count validation passed: %d >= %d", actual_nodes, required_nodes)
        return True

    def monitor_and_scale(self, current_nodes: list[Any]) -> list[Any]:
        """Return healthy nodes and log capacity advice; the legacy name does not imply provisioning."""
        healthy_nodes = [node for node in current_nodes if self._is_healthy(node)]
        health_ratio = len(healthy_nodes) / len(current_nodes) if current_nodes else 0
        logger.info("Node health check: %d/%d healthy", len(healthy_nodes), len(current_nodes))
        if health_ratio < self.auto_scale_threshold:
            logger.warning("Health ratio %.2f below threshold %.2f", health_ratio, self.auto_scale_threshold)
            self._log_capacity_recommendation(healthy_nodes)
        return healthy_nodes

    def _is_healthy(self, node: Any) -> bool:
        try:
            if not hasattr(node, 'health_status') or not hasattr(node, 'last_heartbeat'):
                node_id = getattr(node, "node_id", "unknown")
                logger.warning("Node %s missing health attributes", node_id)
                return False
            is_active = node.health_status == "active"
            time_diff = time.time() - node.last_heartbeat
            return is_active and time_diff < self.health_check_interval
        except (AttributeError, TypeError, ValueError) as ex:
            logger.error("Error checking node health: %s", ex)
            return False

    def _log_capacity_recommendation(self, healthy_nodes: list[Any]) -> None:
        recommendation = {
            "event": "consensus_capacity_recommendation",
            "timestamp": time.time(),
            "healthy_nodes_count": len(healthy_nodes),
            "required_nodes": 3 * self.f + 1,
            "threshold": self.auto_scale_threshold,
        }
        _log_capacity_recommendation(recommendation)
