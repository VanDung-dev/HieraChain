"""
Consensus recovery engine for HieraChain Ledger.
"""

import time
import orjson
import logging
import os
from typing import Any
from datetime import datetime


logger = logging.getLogger(__name__)


class ConsensusRecoveryEngine:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.view_number = 0
        self.recovery_attempts = {}
        self.max_recovery_attempts = config.get("max_recovery_attempts", 3)
        self.view_change_timeout = config.get("view_change_timeout", 10)
        self.node_performance = {}
        self.slow_node_threshold = config.get("slow_node_threshold", 5.0)
        self.silent_node_threshold = config.get("silent_node_threshold", 30.0)
        logger.info("Initialized ConsensusRecoveryEngine")

    def handle_leader_failure(self, failed_leader_id: str, current_view: int) -> bool:
        logger.warning("Leader failure detected: %s in view %d", failed_leader_id, current_view)
        recovery_key = f"leader_failure_{current_view}"
        attempts = self.recovery_attempts.get(recovery_key, 0)
        if attempts >= self.max_recovery_attempts:
            logger.error("Max recovery attempts reached for leader failure in view %d", current_view)
            return False
        new_view = current_view + 1
        recovery_success = self._initiate_view_change(failed_leader_id, new_view)
        self.recovery_attempts[recovery_key] = attempts + 1
        if recovery_success:
            logger.info("Leader failure recovery successful, new view: %d", new_view)
            if recovery_key in self.recovery_attempts:
                del self.recovery_attempts[recovery_key]
        return recovery_success

    def handle_message_ordering_failure(self, failed_messages: list[dict[str, Any]]) -> bool:
        logger.warning(f"Message ordering failure: {len(failed_messages)} messages")
        try:
            ordered_messages = self._reorder_messages(failed_messages)
            for message in ordered_messages:
                if not self._process_message(message):
                    logger.error("Failed to process reordered message: %s", message.get("message_id"))
                    return False
            logger.info("Message ordering recovery successful")
            return True
        except Exception as e:
            logger.error("Message ordering recovery failed: %s", e)
            return False

    def handle_node_performance_issues(self, node_metrics: dict[str, Any]) -> dict[str, Any]:
        isolated_nodes: list[str] = []
        scaling_actions: list[Any] = []
        view_change = False
        current_time = time.time()
        for node_id, metrics in node_metrics.items():
            last_response = metrics.get("last_response", 0)
            response_time = metrics.get("response_time", 0)
            failure_count = metrics.get("failure_count", 0)
            if (current_time - last_response) > self.silent_node_threshold:
                logger.warning("Silent node detected: %s", node_id)
                isolated_nodes.append(node_id)
                view_change = True
            elif response_time > self.slow_node_threshold:
                logger.warning("Slow node detected: %s (response time: %.2fs)", node_id, response_time)
                self.node_performance.setdefault(node_id, []).append(response_time)
            if failure_count > 3:
                logger.warning("High failure count for node: %s (%d failures)", node_id, failure_count)
                isolated_nodes.append(node_id)
                view_change = True
        return {
            "view_change": view_change,
            "isolated_nodes": isolated_nodes,
            "scaling_actions": scaling_actions
        }

    @staticmethod
    def adapt_consensus_parameters(network_conditions: dict[str, Any]) -> dict[str, Any]:
        adapted_params = {}
        avg_latency = network_conditions.get("avg_latency_ms", 100)
        packet_loss = network_conditions.get("packet_loss", 0)
        if avg_latency > 1000:
            adapted_params["view_change_timeout"] = 60.0
            adapted_params["message_timeout"] = 10.0
        elif avg_latency > 500:
            adapted_params["view_change_timeout"] = 45.0
            adapted_params["message_timeout"] = 7.5
        else:
            adapted_params["view_change_timeout"] = 30.0
            adapted_params["message_timeout"] = 5.0
        if packet_loss > 0.1:
            adapted_params["redundancy_factor"] = 3
        elif packet_loss > 0.05:
            adapted_params["redundancy_factor"] = 2
        else:
            adapted_params["redundancy_factor"] = 1
        logger.info("Adapted consensus parameters: %s", adapted_params)
        return adapted_params

    def recover_consensus_state(self, last_known_state: dict[str, Any]) -> bool:
        logger.info("Attempting consensus state recovery")
        try:
            if not self._validate_state_integrity(last_known_state):
                logger.error("State integrity validation failed")
                return False
            self.view_number = last_known_state.get("view_number", 0)
            self.recovery_attempts.clear()
            recovery_event = {
                "event": "consensus_state_recovered",
                "view_number": self.view_number,
                "timestamp": time.time()
            }
            logger.info("Consensus state recovered: %s", orjson.dumps(recovery_event).decode())
            return True
        except Exception as e:
            logger.error("Consensus state recovery failed: %s", e)
            return False

    def _initiate_view_change(self, failed_leader_id: str, new_view: int) -> bool:
        view_change_event = {
            "event": "view_change_initiated",
            "failed_leader": failed_leader_id,
            "old_view": new_view - 1,
            "new_view": new_view,
            "timestamp": time.time()
        }
        logger.info("Initiating view change: %s", orjson.dumps(view_change_event).decode())
        time.sleep(1)
        self.view_number = new_view
        try:
            os.makedirs("log/error_mitigation", exist_ok=True)
            with open("log/error_mitigation/view_changes.log", "a") as f:
                f.write(f"{datetime.now().isoformat()}: {orjson.dumps(view_change_event).decode()}\n")
        except Exception as e:
            logger.error("Failed to log view change: %s", e)
        return True

    @staticmethod
    def _reorder_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(messages, key=lambda msg: (
            msg.get("timestamp", 0),
            msg.get("sequence_number", 0)
        ))

    @staticmethod
    def _process_message(message: dict[str, Any]) -> bool:
        logger.debug("Processing message: %s", message.get("message_id", "unknown"))
        return True

    @staticmethod
    def _validate_state_integrity(state: dict[str, Any]) -> bool:
        required_fields = ["view_number", "timestamp"]
        return all(field in state for field in required_fields)
