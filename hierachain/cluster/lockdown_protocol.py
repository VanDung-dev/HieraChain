"""
Cluster Lockdown Protocol for HieraChain.

Implements cluster-wide lockdown coordination using
gossip-style messaging over the P2P network.
"""

import time
import logging
import threading
from typing import Callable

from hierachain.cluster.lockdown_types import (
    LockdownMessageType,
    LockdownMessage,
    ClusterState,
    QuarantineReport,
)

logger = logging.getLogger(__name__)

_UNSET = ""


def _apply_lock(
    state: ClusterState,
    locked_by: str,
    reason: str,
    timestamp: float,
) -> None:
    """Apply lockdown state."""
    state.is_locked = True
    state.locked_by = locked_by
    state.lock_reason = reason
    state.lock_timestamp = timestamp


def _clear_lock(state: ClusterState) -> None:
    """Clear lockdown state (recovery)."""
    state.is_locked = False
    state.locked_by = ""
    state.lock_reason = ""
    state.locked_nodes.clear()


def _async_broadcast(zmq_node, payload: dict) -> bool:
    """Broadcast payload via ZMQ node, handling event-loop detection."""
    import asyncio
    try:
        asyncio.get_running_loop()
        asyncio.create_task(zmq_node.broadcast(payload))
    except RuntimeError:
        asyncio.run(zmq_node.broadcast(payload))
    return True


def _has_quorum(vote_count: int, total_nodes: int, threshold: float) -> bool:
    """Check whether vote_count / total_nodes meets the threshold."""
    if total_nodes == 0:
        return False
    return (vote_count / total_nodes) >= threshold


def _create_signed_message(
    node_id: str,
    reason: str,
    msg_type: LockdownMessageType,
    secret_key: str,
) -> LockdownMessage:
    """Create a signed LockdownMessage."""
    msg = LockdownMessage(
        node_id=node_id,
        timestamp=time.time(),
        reason=reason,
        message_type=msg_type,
    )
    msg.signature = msg.compute_signature(secret_key)
    return msg


def _validate_incoming_message(
    data: dict,
    sender_id: str,
    secret_key: str,
) -> LockdownMessage | None:
    """Validate an incoming P2P lockdown message.

    Returns the parsed LockdownMessage if valid, None otherwise.
    """
    if data.get("msg_type") != "cluster_lockdown":
        return None

    message = LockdownMessage.from_dict(data)

    if not message.verify_signature(secret_key):
        logger.warning(f"Invalid signature on lockdown message from {sender_id}")
        return None

    if abs(time.time() - message.timestamp) > 300:
        logger.warning(f"Lockdown message expired from {sender_id}")
        return None

    return message


def _invoke_callback(callback: Callable[[], None] | None) -> None:
    """Invoke callback if it is set."""
    if callback:
        callback()


def _register_lockdown_vote(
    lockdown_votes: dict[str, str],
    recovery_votes: set[str],
    registered_nodes: set[str],
    node_id: str,
    reason: str,
) -> None:
    """Register a lockdown vote from a node."""
    registered_nodes.add(node_id)
    lockdown_votes[node_id] = reason
    recovery_votes.discard(node_id)


def _register_recovery_vote(
    lockdown_votes: dict[str, str],
    recovery_votes: set[str],
    registered_nodes: set[str],
    node_id: str,
) -> None:
    """Register a recovery vote from a node."""
    registered_nodes.add(node_id)
    recovery_votes.add(node_id)
    lockdown_votes.pop(node_id, None)


def _parse_quarantine_report(data: dict, secret_key: str) -> QuarantineReport | None:
    """Parse and validate a quarantine report."""
    report = QuarantineReport.from_dict(data)
    if not report.verify_signature(secret_key):
        logger.warning(f"Invalid signature on quarantine report from {report.node_id}")
        return None
    return report


def _add_message_to_history(
    history: list[LockdownMessage],
    message: LockdownMessage,
    max_size: int,
) -> list[LockdownMessage]:
    """Add message to history, trimming if needed."""
    history.append(message)
    if len(history) > max_size:
        return history[-max_size:]
    return history


class ClusterLockdownManager:
    """
    Manages cluster-wide lockdown state and broadcasts.

    Coordinates with ZmqNode for P2P messaging and local
    OrderingService for local lockdown actions.

    Example:
        manager = ClusterLockdownManager(
            node_id="node-1",
            zmq_node=zmq_node,
            local_lockdown_callback=ordering_service.lockdown
        )
        manager.broadcast_lockdown("High CPU usage detected")
    """

    def __init__(
        self,
        node_id: str,
        zmq_node=None,
        local_lockdown_callback: Callable[[], None] | None = None,
        local_recovery_callback: Callable[[], None] | None = None,
        secret_key: str | None = None,

        # 2/3 majority - use 0.66 for proper 3-node quorum
        quorum_threshold: float = 0.66,
    ) -> None:
        """
        Initialize cluster lockdown manager.

        Args:
            node_id: This node's unique identifier.
            zmq_node: ZmqNode instance for P2P messaging (optional).
            local_lockdown_callback: Function to call for local lockdown.
            local_recovery_callback: Function to call for local recovery.
            secret_key: Shared secret for message signing.
            quorum_threshold: Fraction of nodes needed for quorum (default 2/3).
        """
        if secret_key is None or secret_key == _UNSET:
            from hierachain.config.secret_manager import SecretManager
            secret_key = SecretManager().get_secret("HRC_CLUSTER_SECRET", default="")
            if not secret_key:
                logger.warning(
                    "No secure secret_key provided for lockdown protocol. "
                    "Set HRC_CLUSTER_SECRET (or configure HRC_SECRET_BACKEND). "
                    "Authentication may be compromised."
                )

        self.node_id = node_id
        self._zmq_node = zmq_node
        self._local_lockdown = local_lockdown_callback
        self._local_recovery = local_recovery_callback
        self._secret_key: str = secret_key or ""
        self._state = ClusterState()
        self._message_history: list[LockdownMessage] = []
        self._max_history = 100
        self._quorum_threshold = quorum_threshold

        # Track votes from peers
        self._lockdown_votes: dict[str, str] = {}
        self._recovery_votes: set[str] = set()
        self._registered_nodes: set[str] = {node_id}
        self._quarantine_reports: dict[str, QuarantineReport] = {}

        # Thread safety lock for all shared state (RLock for reentrant calls)
        self._lock = threading.RLock()

        # Register message handler if ZMQ node provided
        if self._zmq_node:
            self._zmq_node.set_handler(self._on_message_received)

    @property
    def is_cluster_locked(self) -> bool:
        """Check if cluster is in lockdown state."""
        return self._state.is_locked

    @property
    def cluster_state(self) -> ClusterState:
        """Get current cluster state."""
        return self._state

    def broadcast_lockdown(self, reason: str) -> bool:
        """
        Broadcast lockdown message to all peers.

        Args:
            reason: Reason for lockdown.

        Returns:
            True if broadcast was successful.
        """
        message = _create_signed_message(
            self.node_id,
            reason,
            LockdownMessageType.LOCKDOWN,
            self._secret_key,
        )

        # Update local state
        _apply_lock(self._state, self.node_id, reason, message.timestamp,)
        self._state.locked_nodes.add(self.node_id)

        # Trigger local lockdown
        _invoke_callback(self._local_lockdown)

        # Broadcast to peers
        return self._broadcast_message(message)

    def broadcast_recovery(self) -> bool:
        """
        Broadcast recovery message to lift lockdown.

        Only the node that initiated lockdown should broadcast recovery.

        Returns:
            True if broadcast was successful.
        """
        if not self._state.is_locked:
            logger.warning("Cannot broadcast recovery: not in lockdown")
            return False

        if self._state.locked_by != self.node_id:
            logger.warning(
                "Cannot broadcast recovery: lockdown initiated by %s",
                self._state.locked_by,
            )
            return False

        message = _create_signed_message(
            self.node_id,
            "Recovery",
            LockdownMessageType.RECOVERY,
            self._secret_key,
        )

        # Update local state
        _clear_lock(self._state)

        return self._broadcast_message(message)

    def _broadcast_message(self, message: LockdownMessage) -> bool:
        """Broadcast message to all peers via ZMQ."""
        if not self._zmq_node:
            logger.warning("No ZMQ node configured, cannot broadcast")
            return False

        try:
            _async_broadcast(self._zmq_node, message.to_dict())
            self._add_to_history(message)
            logger.info("Broadcast %s: %s", message.message_type.value, message.reason)
            return True
        except Exception as e:
            logger.error("Failed to broadcast message: %s", e)
            return False

    def _on_message_received(self, data: dict, sender_id: str,) -> None:
        """Handle incoming P2P message."""
        try:
            message = _validate_incoming_message(data, sender_id, self._secret_key,)
            if message:
                self._handle_lockdown_message(message)
        except Exception as e:
            logger.error("Error processing lockdown message: %s", e)

    def _handle_lockdown_message(self, message: LockdownMessage) -> None:
        """Process a validated lockdown message."""
        self._add_to_history(message)

        handlers: dict[LockdownMessageType, Callable[[LockdownMessage], None]] = {
            LockdownMessageType.LOCKDOWN: self._process_lockdown_event,
            LockdownMessageType.RECOVERY: self._process_recovery_event,
            LockdownMessageType.LOCKDOWN_VOTE: self._handle_lockdown_vote,
            LockdownMessageType.RECOVERY_VOTE: self._handle_recovery_vote,
        }

        handler = handlers.get(message.message_type)
        if handler:
            handler(message)

    def _process_lockdown_event(self, message: LockdownMessage) -> None:
        """Handle LOCKDOWN message type."""
        with self._lock:
            if not self._state.is_locked:
                _apply_lock(
                    self._state,
                    message.node_id,
                    message.reason,
                    message.timestamp,
                )
                logger.warning(
                    "Cluster lockdown received from %s: %s",
                    message.node_id, message.reason
                )
                _invoke_callback(self._local_lockdown)

            self._state.locked_nodes.add(message.node_id)

    def _process_recovery_event(self, message: LockdownMessage) -> None:
        """Handle RECOVERY message type."""
        if self._state.locked_by == message.node_id:
            _clear_lock(self._state)
            logger.info(f"Cluster recovery received from {message.node_id}")
            _invoke_callback(self._local_recovery)

    def _handle_lockdown_vote(self, message: LockdownMessage) -> None:
        """Handle a lockdown vote message from a peer."""
        with self._lock:
            _register_lockdown_vote(
                self._lockdown_votes,
                self._recovery_votes,
                self._registered_nodes,
                message.node_id,
                message.reason,
            )
            logger.info(
                "Lockdown vote received from %s: %s",
                message.node_id, message.reason
            )
            if self._check_lockdown_quorum():
                logger.warning("Lockdown quorum reached - triggering cluster lockdown")
                self._trigger_quorum_lockdown()

    def _handle_recovery_vote(self, message: LockdownMessage) -> None:
        """Handle a recovery vote message from a peer."""
        with self._lock:
            _register_recovery_vote(
                self._lockdown_votes,
                self._recovery_votes,
                self._registered_nodes,
                message.node_id,
            )
            logger.info("Recovery vote received from %s", message.node_id)
            if self._check_recovery_quorum():
                logger.info("Recovery quorum reached - lifting cluster lockdown")
                self._trigger_quorum_recovery()

    def _check_lockdown_quorum(self) -> bool:
        """Check if lockdown quorum is reached."""
        with self._lock:
            if self._state.is_locked:
                return False
            return _has_quorum(
                len(self._lockdown_votes),
                len(self._registered_nodes),
                self._quorum_threshold,
            )

    def _check_recovery_quorum(self) -> bool:
        """Check if recovery quorum is reached."""
        with self._lock:
            if not self._state.is_locked:
                return False
            return _has_quorum(
                len(self._recovery_votes),
                len(self._registered_nodes),
                self._quorum_threshold,
            )

    def _trigger_quorum_lockdown(self) -> None:
        """Trigger lockdown after quorum is reached."""
        _apply_lock(
            self._state,
            "quorum",
            "Quorum-based lockdown",
            time.time(),
        )
        self._lockdown_votes.clear()
        _invoke_callback(self._local_lockdown)

    def _trigger_quorum_recovery(self) -> None:
        """Trigger recovery after quorum is reached."""
        _clear_lock(self._state)
        self._recovery_votes.clear()
        _invoke_callback(self._local_recovery)

    def register_node(self, node_id: str) -> None:
        """Register a node in the cluster."""
        with self._lock:
            self._registered_nodes.add(node_id)

    def broadcast_lockdown_vote(self, reason: str) -> bool:
        """
        Broadcast a lockdown vote to all peers.

        Lockdown is only triggered when quorum (2/3 of nodes)
        is reached.

        Args:
            reason: Reason for requesting lockdown.

        Returns:
            True if broadcast was successful.
        """
        message = _create_signed_message(
            self.node_id,
            reason,
            LockdownMessageType.LOCKDOWN_VOTE,
            self._secret_key,
        )

        with self._lock:
            # Register own vote
            _register_lockdown_vote(
                self._lockdown_votes,
                self._recovery_votes,
                self._registered_nodes,
                self.node_id, reason,
            )

            # Check local quorum
            if self._check_lockdown_quorum():
                logger.warning("Lockdown quorum reached locally")
                self._trigger_quorum_lockdown()

        return self._broadcast_message(message)

    def broadcast_recovery_vote(self) -> bool:
        """
        Broadcast a recovery vote to all peers.

        Recovery is only triggered when quorum (2/3 of nodes)
        is reached.

        Returns:
            True if broadcast was successful.
        """
        if not self._state.is_locked:
            logger.warning("Cannot vote for recovery: not in lockdown")
            return False

        message = _create_signed_message(
            self.node_id,
            "Recovery vote",
            LockdownMessageType.RECOVERY_VOTE,
            self._secret_key,
        )

        with self._lock:
            # Register own vote
            _register_recovery_vote(
                self._lockdown_votes,
                self._recovery_votes,
                self._registered_nodes,
                self.node_id,
            )

            # Check local quorum
            if self._check_recovery_quorum():
                logger.info("Recovery quorum reached locally")
                self._trigger_quorum_recovery()

        return self._broadcast_message(message)

    def get_vote_status(self) -> dict[str, int | float | bool]:
        """Get current vote counts and status."""
        with self._lock:
            total = len(self._registered_nodes)
            return {
                "total_nodes": total,
                "lockdown_votes": len(self._lockdown_votes),
                "recovery_votes": len(self._recovery_votes),
                "quorum_threshold": self._quorum_threshold,
                "is_locked": self._state.is_locked,
                "lockdown_quorum_reached": _has_quorum(
                    len(self._lockdown_votes),
                    total,
                    self._quorum_threshold,
                ),
                "recovery_quorum_reached": _has_quorum(
                    len(self._recovery_votes),
                    total,
                    self._quorum_threshold,
                ),
            }

    def _add_to_history(self, message: LockdownMessage) -> None:
        """Add message to history with size limit."""
        self._message_history = _add_message_to_history(
            self._message_history, message, self._max_history,
        )

    def get_history(self) -> list[dict[str, str | float]]:
        """Get message history as list of dicts."""
        return [m.to_dict() for m in self._message_history]

    def broadcast_quarantine_report(
        self,
        pending_event_ids: list[str],
        last_block_index: int = 0,
        last_block_hash: str = "",
    ) -> bool:
        """
        Broadcast quarantine report to peers before flushing (Last Breath).

        This sends fingerprints of pending events to peers so they can
        identify gaps in their own state after recovery.

        Args:
            pending_event_ids: List of pending event IDs to report.
            last_block_index: Index of last committed block.
            last_block_hash: Hash of last committed block.

        Returns:
            True if broadcast was successful.
        """
        report = QuarantineReport(
            node_id=self.node_id,
            timestamp=time.time(),
            pending_event_ids=pending_event_ids[:100],  # Limit to 100
            last_block_index=last_block_index,
            last_block_hash=last_block_hash,
            total_pending=len(pending_event_ids),
        )
        report.signature = report.compute_signature(self._secret_key)

        # Store locally for reference
        self._quarantine_reports[self.node_id] = report

        logger.info(
            "Broadcasting quarantine report: %s events, block %s",
            len(pending_event_ids), last_block_index
        )

        return self._broadcast_report(report)

    def _broadcast_report(self, report: QuarantineReport) -> bool:
        """Broadcast a QuarantineReport to peers."""
        if not self._zmq_node:
            logger.warning("No ZMQ node configured, cannot broadcast report")
            return False

        try:
            _async_broadcast(self._zmq_node, report.to_dict())
            return True
        except Exception as e:
            logger.error(f"Failed to broadcast quarantine report: {e}")
            return False

    def receive_quarantine_report(self, data: dict) -> QuarantineReport | None:
        """
        Process a received quarantine report from a peer.

        Args:
            data: Dictionary with report data.

        Returns:
            The parsed QuarantineReport if valid, None otherwise.
        """
        try:
            report = _parse_quarantine_report(data, self._secret_key)
            if not report:
                return None

            self._quarantine_reports[report.node_id] = report
            logger.info(
                f"Received quarantine report from "
                f"{report.node_id}: "
                f"{report.total_pending} events"
            )
            return report
        except Exception as e:
            logger.error(
                "Error processing quarantine report from %s: %s",
                data.get("node_id", "unknown"), e
            )
            return None

    def get_quarantine_reports(self) -> dict[str, QuarantineReport]:
        """Get all stored quarantine reports."""
        return self._quarantine_reports.copy()
