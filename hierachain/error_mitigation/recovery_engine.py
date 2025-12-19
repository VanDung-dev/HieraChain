"""
Error Mitigation Recovery Engine Module

This module provides automated recovery mechanisms. It handles network
recovery, resource scaling, consensus recovery, and other critical
recovery operations.
"""

import time
import json
import logging
import asyncio
from typing import Any
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RecoveryError(Exception):
    """Raised when recovery operations fail"""
    pass


class NetworkRecoveryEngine:
    """
    Handles network-related recoveries in consensus processes

    Manages network timeouts, redundant paths, partition detection,
    and automatic recovery from network issues affecting consensus.
    """

    def __init__(self, consensus_config: dict[str, Any]):
        """
        Initialize network recovery engine

        Args:
            consensus_config: Configuration dictionary with network parameters
        """
        self.config = consensus_config
        self.timeout_base = 5.0  # Base timeout in seconds
        self.timeout_multiplier = self.config.get("timeout_multiplier", 2.0)
        self.redundancy_factor = self.config.get("redundancy_factor", 2)
        self.max_retries = self.config.get("max_retries", 3)
        self.latency_history = []
        self.network_health = {}
        self.partition_detected = False

        logger.info(f"Initialized NetworkRecoveryEngine with redundancy_factor={self.redundancy_factor}")

    def adjust_timeout(self, latency_history_input: list[float]) -> float:
        """
        Dynamically adjust timeouts based on network latency history

        Args:
            latency_history_input: List of recent latency measurements in milliseconds

        Returns:
            float: Adjusted timeout value in seconds
        """
        if not latency_history_input:
            return self.timeout_base * self.timeout_multiplier

        # Calculate statistics
        avg_latency = sum(latency_history_input) / len(latency_history_input)
        max_latency = max(latency_history_input)

        # Adjust timeout based on network conditions
        network_factor = 1 + (avg_latency / 1000)  # Convert ms to s
        volatility_factor = 1 + (max_latency - avg_latency) / 1000

        calculated_timeout = self.timeout_base * network_factor * volatility_factor * self.timeout_multiplier

        # Ensure timeout doesn't exceed maximum
        max_timeout = self.config.get("max_timeout", 30.0)
        calculated_timeout = min(calculated_timeout, max_timeout)

        logger.info(f"Timeout adjusted to {calculated_timeout:.2f}s based on avg latency {avg_latency:.1f}ms")
        return calculated_timeout

    async def send_with_redundancy(self, message: dict[str, Any], target_nodes: list[str]) -> dict[str, Any]:
        """
        Send message via multiple redundant paths

        Args:
            message: Message to send
            target_nodes: List of target node identifiers

        Returns:
            Dict: Response from first successful path

        Raises:
            RecoveryError: If all paths fail
        """
        if not target_nodes:
            raise RecoveryError("No target nodes provided for redundant sending")

        futures = []

        # Create multiple sending tasks
        for path_id in range(min(self.redundancy_factor, len(target_nodes))):
            target_node = target_nodes[path_id % len(target_nodes)]
            future = asyncio.create_task(self._send_via_path(message, target_node, path_id))
            futures.append(future)

        try:
            # Wait for first successful response
            done, pending = await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)

            # Cancel pending tasks
            for task in pending:
                task.cancel()

            # Return first successful result
            for task in done:
                if not task.exception():
                    result = await task
                    logger.info(f"Message sent successfully via redundant path")
                    return result

            # If all tasks failed
            raise RecoveryError("All redundant paths failed")

        except asyncio.TimeoutError:
            logger.error("Redundant sending timed out")
            raise RecoveryError("Network timeout on all paths")

    async def _send_via_path(self, message: dict[str, Any], target_node: str, path_id: int) -> dict[str, Any]:
        """
        Send message via specific path

        Args:
            message: Message to send
            target_node: Target node identifier
            path_id: Path identifier for logging

        Returns:
            Dict: Response from target node
        """
        # Use the message parameter to avoid unused parameter warning
        _ = message  # Explicitly acknowledge the parameter is used
        
        start_time = time.time()

        try:
            # Simulate network communication (in real implementation, this would be actual network code)
            await asyncio.sleep(0.1)  # Simulate network delay

            # Record latency
            latency = (time.time() - start_time) * 1000  # Convert to ms
            self.latency_history.append(latency)

            # Keep only recent latency history
            if len(self.latency_history) > 100:
                self.latency_history = self.latency_history[-50:]

            response = {
                "status": "success",
                "target_node": target_node,
                "path_id": path_id,
                "latency_ms": latency,
                "timestamp": time.time(),
                "message_content": str(message)  # Actually use the message parameter
            }

            logger.debug(f"Message sent via path {path_id} to {target_node} (latency: {latency:.1f}ms)")
            return response

        except Exception as e:
            logger.error(f"Path {path_id} to {target_node} failed: {e}")
            raise RecoveryError(f"Path {path_id} failed: {str(e)}")

    def monitor_network_health(self) -> dict[str, Any]:
        """
        Monitor network health and detect partitions

        Returns:
            Dict: Network health status
        """
        health_status = {
            "timestamp": time.time(),
            "avg_latency_ms": 0,
            "max_latency_ms": 0,
            "partition_detected": False,
            "healthy_paths": 0,
            "total_paths": self.redundancy_factor
        }

        if self.latency_history:
            health_status["avg_latency_ms"] = sum(self.latency_history) / len(self.latency_history)
            health_status["max_latency_ms"] = max(self.latency_history)

        # Detect network partition (simplified logic)
        if health_status["avg_latency_ms"] > 5000:  # 5 second threshold
            self.partition_detected = True
            health_status["partition_detected"] = True
            logger.warning("Network partition detected based on high latency")
            self._initiate_view_change()

        return health_status

    def _initiate_view_change(self) -> None:
        """
        Initiate view change due to network issues
        """
        view_change_event = {
            "event": "view_change_initiated",
            "reason": "network_partition",
            "timestamp": time.time(),
            "network_health": self.monitor_network_health()
        }

        logger.info(f"View change initiated: {json.dumps(view_change_event)}")

        # Send alert
        self._send_alert("Network partition detected, view change initiated")

    @staticmethod
    def _send_alert(message: str) -> None:
        """
        Send alert about network issues

        Args:
            message: Alert message
        """
        alert = {
            "event": "network_alert",
            "message": message,
            "timestamp": time.time(),
            "severity": "high"
        }

        logger.warning(f"Network alert: {message}")

        # Write to alert log
        try:
            os.makedirs("log/error_mitigation", exist_ok=True)
            with open("log/error_mitigation/network_alerts.log", "a") as f:
                f.write(f"{datetime.now().isoformat()}: {json.dumps(alert)}\n")
        except Exception as e:
            logger.error(f"Failed to write network alert: {e}")


class AutoScaler:
    """
    Manages automatic scaling of resources and nodes

    Handles scaling decisions, resource allocation, and coordination
    with external orchestration systems like Kubernetes.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize auto scaler

        Args:
            config: Configuration dictionary with scaling parameters
        """
        self.config = config
        self.enabled = config.get("auto_scale", False)
        self.scale_up_threshold = config.get("scale_up_threshold", 0.8)
        self.scale_down_threshold = config.get("scale_down_threshold", 0.3)
        self.min_nodes = config.get("min_nodes", 4)  # For BFT n >= 3f + 1
        self.max_nodes = config.get("max_nodes", 16)
        self.cooldown_period = config.get("cooldown_period", 300)  # 5 minutes
        self.last_scaling_action = 0

        logger.info(f"Initialized AutoScaler (enabled={self.enabled})")

    def scale_up(self, resource_type: str, current_load: float) -> bool:
        """
        Scale up resources or nodes

        Args:
            resource_type: Type of resource (cpu, memory, nodes)
            current_load: Current load percentage (0-1)

        Returns:
            bool: True if scaling was triggered
        """
        if not self.enabled:
            logger.info("Auto-scaling disabled, scale up ignored")
            return False

        if not self._can_scale():
            logger.info("Scaling cooldown period active")
            return False

        if current_load < self.scale_up_threshold:
            logger.debug(f"Load {current_load:.2f} below scale up threshold {self.scale_up_threshold}")
            return False

        scaling_event = {
            "event": "auto_scale_up",
            "resource_type": resource_type,
            "current_load": current_load,
            "threshold": self.scale_up_threshold,
            "timestamp": time.time()
        }

        logger.info(f"Scaling up {resource_type}: {json.dumps(scaling_event)}")

        # Execute scaling
        success = self._execute_scaling("up", resource_type)
        if success:
            self.last_scaling_action = time.time()
            self._log_scaling_event(scaling_event)

        return success

    def scale_down(self, resource_type: str, current_load: float) -> bool:
        """
        Scale down resources or nodes

        Args:
            resource_type: Type of resource (cpu, memory, nodes)
            current_load: Current load percentage (0-1)

        Returns:
            bool: True if scaling was triggered
        """
        if not self.enabled:
            return False

        if not self._can_scale():
            return False

        if current_load > self.scale_down_threshold:
            return False

        # Special check for nodes - don't scale below minimum for BFT
        if resource_type == "nodes" and self._get_current_node_count() <= self.min_nodes:
            logger.info(f"Cannot scale down nodes below minimum {self.min_nodes}")
            return False

        scaling_event = {
            "event": "auto_scale_down",
            "resource_type": resource_type,
            "current_load": current_load,
            "threshold": self.scale_down_threshold,
            "timestamp": time.time()
        }

        logger.info(f"Scaling down {resource_type}: {json.dumps(scaling_event)}")

        success = self._execute_scaling("down", resource_type)
        if success:
            self.last_scaling_action = time.time()
            self._log_scaling_event(scaling_event)

        return success

    def _can_scale(self) -> bool:
        """
        Check if scaling is allowed (cooldown period)

        Returns:
            bool: True if scaling is allowed
        """
        return (time.time() - self.last_scaling_action) >= self.cooldown_period

    def _execute_scaling(self, direction: str, resource_type: str) -> bool:
        """
        Execute actual scaling operation

        Args:
            direction: 'up' or 'down'
            resource_type: Type of resource to scale

        Returns:
            bool: True if scaling succeeded
        """
        try:
            if resource_type == "nodes":
                return self._scale_nodes(direction)
            elif resource_type in ["cpu", "memory"]:
                return self._scale_resources(direction, resource_type)
            else:
                logger.error(f"Unknown resource type for scaling: {resource_type}")
                return False
        except Exception as e:
            logger.error(f"Scaling execution failed: {e}")
            return False

    def _scale_nodes(self, direction: str) -> bool:
        """
        Scale consensus nodes up or down

        Args:
            direction: 'up' or 'down'

        Returns:
            bool: True if successful
        """
        current_nodes = self._get_current_node_count()

        if direction == "up" and current_nodes < self.max_nodes:
            # In real implementation, call orchestrator API
            logger.info(f"Adding consensus node (current: {current_nodes})")
            return True
        elif direction == "down" and current_nodes > self.min_nodes:
            logger.info(f"Removing consensus node (current: {current_nodes})")
            return True

        return False

    @staticmethod
    def _scale_resources(direction: str, resource_type: str) -> bool:
        """
        Scale CPU or memory resources

        Args:
            direction: 'up' or 'down'
            resource_type: 'cpu' or 'memory'

        Returns:
            bool: True if successful
        """
        # In real implementation, this would adjust container/VM resources
        logger.info(f"Scaling {resource_type} {direction}")
        return True

    @staticmethod
    def _get_current_node_count() -> int:
        """
        Get current number of consensus nodes

        Returns:
            int: Number of current nodes
        """
        # In real implementation, query actual consensus system
        return 4  # Default for testing

    @staticmethod
    def _log_scaling_event(event: dict[str, Any]) -> None:
        """
        Log scaling events for audit

        Args:
            event: Scaling event details
        """
        try:
            os.makedirs("log/error_mitigation", exist_ok=True)
            with open("log/error_mitigation/scaling_events.log", "a") as f:
                f.write(f"{datetime.now().isoformat()}: {json.dumps(event)}\n")
        except Exception as e:
            logger.error(f"Failed to log scaling event: {e}")


class ConsensusRecoveryEngine:
    """
    Handles consensus-related failures and recovery

    Manages leader election failures, view changes, message
    ordering issues, and consensus state recovery.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize consensus recovery engine

        Args:
            config: Configuration dictionary with consensus parameters
        """
        self.config = config
        self.view_number = 0
        self.recovery_attempts = {}
        self.max_recovery_attempts = config.get("max_recovery_attempts", 3)
        self.view_change_timeout = config.get("view_change_timeout", 10)

        # Node behavior tracking
        self.node_performance = {}  # Track node response times and failures
        self.slow_node_threshold = config.get("slow_node_threshold", 5.0)  # seconds
        self.silent_node_threshold = config.get("silent_node_threshold", 30.0)  # seconds

        logger.info("Initialized ConsensusRecoveryEngine")

    def handle_leader_failure(self, failed_leader_id: str, current_view: int) -> bool:
        """
        Handle leader node failure

        Args:
            failed_leader_id: ID of the failed leader
            current_view: Current view number

        Returns:
            bool: True if recovery was successful
        """
        logger.warning(f"Leader failure detected: {failed_leader_id} in view {current_view}")

        recovery_key = f"leader_failure_{current_view}"
        attempts = self.recovery_attempts.get(recovery_key, 0)

        if attempts >= self.max_recovery_attempts:
            logger.error(f"Max recovery attempts reached for leader failure in view {current_view}")
            return False

        # Initiate view change
        new_view = current_view + 1
        recovery_success = self._initiate_view_change(failed_leader_id, new_view)

        # Update recovery attempts
        self.recovery_attempts[recovery_key] = attempts + 1

        if recovery_success:
            logger.info(f"Leader failure recovery successful, new view: {new_view}")
            # Clear recovery attempts on success
            if recovery_key in self.recovery_attempts:
                del self.recovery_attempts[recovery_key]

        return recovery_success

    def handle_message_ordering_failure(self, failed_messages: list[dict[str, Any]]) -> bool:
        """
        Handle message ordering failures

        Args:
            failed_messages: List of messages that failed to be ordered

        Returns:
            bool: True if recovery was successful
        """
        logger.warning(f"Message ordering failure: {len(failed_messages)} messages")

        try:
            # Re-queue messages with proper ordering
            ordered_messages = self._reorder_messages(failed_messages)

            # Attempt to process reordered messages
            for message in ordered_messages:
                if not self._process_message(message):
                    logger.error(f"Failed to process reordered message: {message.get('message_id')}")
                    return False

            logger.info("Message ordering recovery successful")
            return True

        except Exception as e:
            logger.error(f"Message ordering recovery failed: {e}")
            return False

    def handle_node_performance_issues(self, node_metrics: dict[str, Any]) -> dict[str, Any]:
        """
        Handle node performance issues based on metrics

        Args:
            node_metrics: Dictionary of node performance metrics

        Returns:
            Dict: Recovery actions to take
        """
        actions = {
            "view_change": False,
            "isolated_nodes": [],
            "scaling_actions": []
        }

        current_time = time.time()

        for node_id, metrics in node_metrics.items():
            last_response = metrics.get("last_response", 0)
            response_time = metrics.get("response_time", 0)
            failure_count = metrics.get("failure_count", 0)

            # Check for silent nodes
            if (current_time - last_response) > self.silent_node_threshold:
                logger.warning(f"Silent node detected: {node_id}")
                actions["isolated_nodes"].append(node_id)
                actions["view_change"] = True

            # Check for slow nodes
            elif response_time > self.slow_node_threshold:
                logger.warning(f"Slow node detected: {node_id} (response time: {response_time}s)")
                # Track slow nodes but don't necessarily trigger view change unless multiple
                self.node_performance.setdefault(node_id, []).append(response_time)

            # Check for high failure count
            if failure_count > 3:
                logger.warning(f"High failure count for node: {node_id} ({failure_count} failures)")
                actions["isolated_nodes"].append(node_id)
                actions["view_change"] = True

        return actions

    @staticmethod
    def adapt_consensus_parameters(network_conditions: dict[str, Any]) -> dict[str, Any]:
        """
        Adapt consensus parameters based on network conditions

        Args:
            network_conditions: Current network conditions

        Returns:
            Dict: Updated consensus parameters
        """
        adapted_params = {}

        avg_latency = network_conditions.get("avg_latency_ms", 100)
        packet_loss = network_conditions.get("packet_loss", 0)

        # Adjust timeouts based on network conditions
        if avg_latency > 1000:  # 1 second
            adapted_params["view_change_timeout"] = 60.0
            adapted_params["message_timeout"] = 10.0
        elif avg_latency > 500:  # 0.5 second
            adapted_params["view_change_timeout"] = 45.0
            adapted_params["message_timeout"] = 7.5
        else:
            adapted_params["view_change_timeout"] = 30.0
            adapted_params["message_timeout"] = 5.0

        # Adjust for packet loss
        if packet_loss > 0.1:  # 10% packet loss
            adapted_params["redundancy_factor"] = 3
        elif packet_loss > 0.05:  # 5% packet loss
            adapted_params["redundancy_factor"] = 2
        else:
            adapted_params["redundancy_factor"] = 1

        logger.info(f"Adapted consensus parameters: {adapted_params}")
        return adapted_params

    def recover_consensus_state(self, last_known_state: dict[str, Any]) -> bool:
        """
        Recover consensus state from last known good state

        Args:
            last_known_state: Last known consensus state

        Returns:
            bool: True if recovery was successful
        """
        logger.info("Attempting consensus state recovery")

        try:
            # Validate state integrity
            if not self._validate_state_integrity(last_known_state):
                logger.error("State integrity validation failed")
                return False

            # Restore state
            self.view_number = last_known_state.get("view_number", 0)

            # Clear any stale recovery attempts
            self.recovery_attempts.clear()

            recovery_event = {
                "event": "consensus_state_recovered",
                "view_number": self.view_number,
                "timestamp": time.time()
            }

            logger.info(f"Consensus state recovered: {json.dumps(recovery_event)}")
            return True

        except Exception as e:
            logger.error(f"Consensus state recovery failed: {e}")
            return False

    def _initiate_view_change(self, failed_leader_id: str, new_view: int) -> bool:
        """
        Initiate view change process

        Args:
            failed_leader_id: ID of failed leader
            new_view: New view number

        Returns:
            bool: True if view change succeeded
        """
        view_change_event = {
            "event": "view_change_initiated",
            "failed_leader": failed_leader_id,
            "old_view": new_view - 1,
            "new_view": new_view,
            "timestamp": time.time()
        }

        logger.info(f"Initiating view change: {json.dumps(view_change_event)}")

        # Simulate view change process
        time.sleep(1)  # Simulate view change time

        self.view_number = new_view

        # Log view change
        try:
            os.makedirs("log/error_mitigation", exist_ok=True)
            with open("log/error_mitigation/view_changes.log", "a") as f:
                f.write(f"{datetime.now().isoformat()}: {json.dumps(view_change_event)}\n")
        except Exception as e:
            logger.error(f"Failed to log view change: {e}")

        return True

    @staticmethod
    def _reorder_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Reorder messages based on timestamp and sequence

        Args:
            messages: List of messages to reorder

        Returns:
            List: Properly ordered messages
        """
        # Sort by timestamp, then by sequence number if available
        return sorted(messages, key=lambda msg: (
            msg.get("timestamp", 0),
            msg.get("sequence_number", 0)
        ))

    @staticmethod
    def _process_message(message: dict[str, Any]) -> bool:
        """
        Process a single message

        Args:
            message: Message to process

        Returns:
            bool: True if processing succeeded
        """
        # Simulate message processing
        logger.debug(f"Processing message: {message.get('message_id', 'unknown')}")
        return True

    @staticmethod
    def _validate_state_integrity(state: dict[str, Any]) -> bool:
        """
        Validate consensus state integrity

        Args:
            state: State to validate

        Returns:
            bool: True if state is valid
        """
        required_fields = ["view_number", "timestamp"]
        return all(field in state for field in required_fields)


class BackupRecoveryEngine:
    """
    Manages data backup and restoration operations

    Handles automated backups, integrity verification, and
    recovery from backup data when needed.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize backup recovery engine

        Args:
            config: Configuration dictionary with backup parameters
        """
        self.config = config
        self.backup_locations = config.get("locations", ["primary"])
        self.integrity_check = config.get("integrity_check", "sha256")
        self.max_recovery_attempts = config.get("max_recovery_attempts", 3)

        logger.info(f"Initialized BackupRecoveryEngine with {len(self.backup_locations)} locations")

    def recover_from_backup(self, backup_path: str) -> bool:
        """
        Recover data from backup

        Args:
            backup_path: Path to backup file

        Returns:
            bool: True if recovery succeeded
        """
        logger.info(f"Attempting recovery from backup: {backup_path}")

        for attempt in range(self.max_recovery_attempts):
            try:
                # Verify backup integrity
                if not self._verify_backup_integrity(backup_path):
                    logger.error(f"Backup integrity check failed: {backup_path}")
                    continue

                # Restore data
                if self._restore_data(backup_path):
                    logger.info(f"Recovery successful from {backup_path}")
                    return True

            except Exception as e:
                logger.error(f"Recovery attempt {attempt + 1} failed: {e}")
                if attempt < self.max_recovery_attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        logger.error(f"All recovery attempts failed for {backup_path}")
        return False

    def _verify_backup_integrity(self, backup_path: str) -> bool:
        """
        Verify backup file integrity

        Args:
            backup_path: Path to backup file

        Returns:
            bool: True if integrity check passes
        """
        if not os.path.exists(backup_path):
            logger.error(f"Backup file does not exist: {backup_path}")
            return False

        try:
            # Calculate hash of backup file
            import hashlib
            hash_func = hashlib.sha256() if self.integrity_check == "sha256" else hashlib.md5()

            with open(backup_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)

            calculated_hash = hash_func.hexdigest()

            # Compare with stored hash (would be in metadata file)
            metadata_path = backup_path + ".meta"
            if os.path.exists(metadata_path):
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    stored_hash = metadata.get("hash")

                    if calculated_hash == stored_hash:
                        logger.info("Backup integrity verification passed")
                        return True
                    else:
                        logger.error("Backup integrity verification failed: hash mismatch")
                        return False

            logger.warning("No metadata file found, skipping hash verification")
            return True

        except Exception as e:
            logger.error(f"Integrity verification failed: {e}")
            return False

    @staticmethod
    def _restore_data(backup_path: str) -> bool:
        """
        Restore data from backup file

        Args:
            backup_path: Path to backup file

        Returns:
            bool: True if restoration succeeded
        """
        try:
            # Simulate data restoration
            logger.info(f"Restoring data from {backup_path}")

            # In real implementation, this would extract and restore actual data
            time.sleep(1)  # Simulate restoration time

            restoration_event = {
                "event": "data_restored_from_backup",
                "backup_path": backup_path,
                "timestamp": time.time()
            }

            logger.info(f"Data restoration completed: {json.dumps(restoration_event)}")

            # Log restoration event
            os.makedirs("log/error_mitigation", exist_ok=True)
            with open("log/error_mitigation/restoration_events.log", "a") as f:
                f.write(f"{datetime.now().isoformat()}: {json.dumps(restoration_event)}\n")

            return True

        except Exception as e:
            logger.error(f"Data restoration failed: {e}")
            return False


# Factory function for creating recovery engines
def create_recovery_engine(engine_type: str, config: dict[str, Any]):
    """
    Factory function to create appropriate recovery engine

    Args:
        engine_type: Type of recovery engine to create
        config: Configuration for the recovery engine

    Returns:
        Recovery engine instance

    Raises:
        ValueError: If engine type is unknown
    """
    engines = {
        "network": NetworkRecoveryEngine,
        "autoscaler": AutoScaler,
        "consensus": ConsensusRecoveryEngine,
        "backup": BackupRecoveryEngine
    }

    if engine_type not in engines:
        raise ValueError(f"Unknown recovery engine type: {engine_type}")

    return engines[engine_type](config)
