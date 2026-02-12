"""
Cluster Lockdown Protocol for HieraChain.

This module implements cluster-wide lockdown coordination using
gossip-style messaging over the P2P network.

Features:
- Broadcast lockdown events to all peers
- Receive and process lockdown messages from peers
- Track cluster-wide lockdown state
- Support recovery broadcasts
"""

import time
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)


class LockdownMessageType(Enum):
    """Types of lockdown-related messages."""
    LOCKDOWN = "lockdown"
    RECOVERY = "recovery"
    HEARTBEAT = "heartbeat"
    LOCKDOWN_VOTE = "lockdown_vote"
    RECOVERY_VOTE = "recovery_vote"
    QUARANTINE_REPORT = "quarantine_report"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"


@dataclass
class LockdownMessage:
    """
    Cluster lockdown message for P2P broadcast.

    Attributes:
        node_id: ID of the node sending the message.
        timestamp: Unix timestamp when message was created.
        reason: Reason for lockdown (for LOCKDOWN type).
        message_type: Type of message (lockdown, recovery, heartbeat).
        signature: HMAC signature for authenticity (optional).
    """
    node_id: str
    timestamp: float
    reason: str
    message_type: LockdownMessageType
    signature: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "msg_type": "cluster_lockdown",
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "lockdown_type": self.message_type.value,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LockdownMessage":
        """Create from dictionary."""
        return cls(
            node_id=data.get("node_id", "unknown"),
            timestamp=data.get("timestamp", 0.0),
            reason=data.get("reason", ""),
            message_type=LockdownMessageType(data.get("lockdown_type", "lockdown")),
            signature=data.get("signature", ""),
        )

    def compute_signature(self, secret_key: str) -> str:
        """Compute HMAC signature for message."""
        message_data = f"{self.node_id}:{self.timestamp}:{self.reason}:{self.message_type.value}"
        return hashlib.sha256(f"{message_data}:{secret_key}".encode()).hexdigest()[:32]

    def verify_signature(self, secret_key: str) -> bool:
        """Verify message signature."""
        expected = self.compute_signature(secret_key)
        return self.signature == expected


@dataclass
class ClusterState:
    """Current state of the cluster lockdown."""
    is_locked: bool = False
    locked_by: str = ""
    lock_reason: str = ""
    lock_timestamp: float = 0.0
    locked_nodes: set = field(default_factory=set)


@dataclass
class QuarantineReport:
    """
    Report sent by a node before flushing its event pool (Last Breath).

    Contains fingerprints of pending events that other nodes can use
    to identify gaps in their own state after recovery.

    Attributes:
        node_id: ID of the reporting node.
        timestamp: When the report was created.
        pending_event_ids: List of event IDs pending in the pool.
        last_block_index: Index of the last committed block.
        last_block_hash: Hash of the last committed block.
        total_pending: Total number of pending events.
        signature: HMAC signature for authenticity.
    """
    node_id: str
    timestamp: float
    pending_event_ids: list = field(default_factory=list)
    last_block_index: int = 0
    last_block_hash: str = ""
    total_pending: int = 0
    signature: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "msg_type": "cluster_lockdown",
            "lockdown_type": LockdownMessageType.QUARANTINE_REPORT.value,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "pending_event_ids": self.pending_event_ids,
            "last_block_index": self.last_block_index,
            "last_block_hash": self.last_block_hash,
            "total_pending": self.total_pending,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuarantineReport":
        """Create from dictionary."""
        return cls(
            node_id=data.get("node_id", "unknown"),
            timestamp=data.get("timestamp", 0.0),
            pending_event_ids=data.get("pending_event_ids", []),
            last_block_index=data.get("last_block_index", 0),
            last_block_hash=data.get("last_block_hash", ""),
            total_pending=data.get("total_pending", 0),
            signature=data.get("signature", ""),
        )

    def compute_signature(self, secret_key: str) -> str:
        """Compute HMAC signature for report."""
        msg = f"{self.node_id}:{self.timestamp}:{self.last_block_index}"
        return hashlib.sha256(f"{msg}:{secret_key}".encode()).hexdigest()[:32]

    def verify_signature(self, secret_key: str) -> bool:
        """Verify report signature."""
        return self.signature == self.compute_signature(secret_key)


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
        secret_key: str = "default_secret_key",
        quorum_threshold: float = 0.66,  # 2/3 majority - use 0.66 for proper 3-node quorum
    ):
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
        self.node_id = node_id
        self._zmq_node = zmq_node
        self._local_lockdown = local_lockdown_callback
        self._local_recovery = local_recovery_callback
        self._secret_key = secret_key
        self._state = ClusterState()
        self._message_history: list[LockdownMessage] = []
        self._max_history = 100
        self._quorum_threshold = quorum_threshold
        
        # Track votes from peers
        self._lockdown_votes: dict[str, str] = {}  # node_id -> reason
        self._recovery_votes: set[str] = set()  # node_ids
        self._registered_nodes: set[str] = {node_id}  # All known nodes
        self._quarantine_reports: dict[str, QuarantineReport] = {}

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
        message = LockdownMessage(
            node_id=self.node_id,
            timestamp=time.time(),
            reason=reason,
            message_type=LockdownMessageType.LOCKDOWN,
        )
        message.signature = message.compute_signature(self._secret_key)

        # Update local state
        self._state.is_locked = True
        self._state.locked_by = self.node_id
        self._state.lock_reason = reason
        self._state.lock_timestamp = message.timestamp
        self._state.locked_nodes.add(self.node_id)

        # Trigger local lockdown
        if self._local_lockdown:
            self._local_lockdown()

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
                f"Cannot broadcast recovery: lockdown initiated by {self._state.locked_by}"
            )
            return False

        message = LockdownMessage(
            node_id=self.node_id,
            timestamp=time.time(),
            reason="Recovery",
            message_type=LockdownMessageType.RECOVERY,
        )
        message.signature = message.compute_signature(self._secret_key)

        # Update local state
        self._state.is_locked = False
        self._state.locked_by = ""
        self._state.lock_reason = ""
        self._state.locked_nodes.clear()

        return self._broadcast_message(message)

    def _broadcast_message(self, message: LockdownMessage) -> bool:
        """Broadcast message to all peers via ZMQ."""
        if not self._zmq_node:
            logger.warning("No ZMQ node configured, cannot broadcast")
            return False

        try:
            import asyncio
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self._zmq_node.broadcast(message.to_dict()))
            except RuntimeError:
                asyncio.run(self._zmq_node.broadcast(message.to_dict()))

            self._add_to_history(message)
            logger.info(f"Broadcast {message.message_type.value}: {message.reason}")
            return True

        except Exception as e:
            logger.error(f"Failed to broadcast message: {e}")
            return False

    def _on_message_received(self, data: dict, sender_id: str) -> None:
        """Handle incoming P2P message."""
        if data.get("msg_type") != "cluster_lockdown":
            return  # Not a lockdown message

        try:
            message = LockdownMessage.from_dict(data)

            # Verify signature
            if not message.verify_signature(self._secret_key):
                logger.warning(f"Invalid signature on lockdown message from {sender_id}")
                return

            # Prevent replay attacks (5 minute window)
            if abs(time.time() - message.timestamp) > 300:
                logger.warning(f"Lockdown message expired from {sender_id}")
                return

            self._handle_lockdown_message(message)

        except Exception as e:
            logger.error(f"Error processing lockdown message: {e}")

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
        if not self._state.is_locked:
            self._state.is_locked = True
            self._state.locked_by = message.node_id
            self._state.lock_reason = message.reason
            self._state.lock_timestamp = message.timestamp

            logger.warning(
                f"Cluster lockdown received from {message.node_id}: {message.reason}"
            )

            # Trigger local lockdown
            if self._local_lockdown:
                self._local_lockdown()

        self._state.locked_nodes.add(message.node_id)

    def _process_recovery_event(self, message: LockdownMessage) -> None:
        """Handle RECOVERY message type."""
        if self._state.locked_by == message.node_id:
            self._state.is_locked = False
            self._state.locked_by = ""
            self._state.lock_reason = ""
            self._state.locked_nodes.clear()
            logger.info(f"Cluster recovery received from {message.node_id}")

            # Trigger local recovery callback
            if self._local_recovery:
                self._local_recovery()

    def _handle_lockdown_vote(self, message: LockdownMessage) -> None:
        """Handle a lockdown vote message from a peer."""
        self._registered_nodes.add(message.node_id)
        self._lockdown_votes[message.node_id] = message.reason
        # Clear any recovery vote from this node
        self._recovery_votes.discard(message.node_id)

        logger.info(
            f"Lockdown vote received from {message.node_id}: {message.reason}"
        )

        # Check if quorum is reached
        if self._check_lockdown_quorum():
            logger.warning("Lockdown quorum reached - triggering cluster lockdown")
            self._trigger_quorum_lockdown()

    def _handle_recovery_vote(self, message: LockdownMessage) -> None:
        """Handle a recovery vote message from a peer."""
        self._registered_nodes.add(message.node_id)
        self._recovery_votes.add(message.node_id)
        # Clear any lockdown vote from this node
        if message.node_id in self._lockdown_votes:
            del self._lockdown_votes[message.node_id]

        logger.info(f"Recovery vote received from {message.node_id}")

        # Check if quorum is reached
        if self._check_recovery_quorum():
            logger.info("Recovery quorum reached - lifting cluster lockdown")
            self._trigger_quorum_recovery()

    def _check_lockdown_quorum(self) -> bool:
        """Check if lockdown quorum is reached."""
        if self._state.is_locked:
            return False  # Already in lockdown

        total = len(self._registered_nodes)
        if total == 0:
            return False

        votes = len(self._lockdown_votes)
        return (votes / total) >= self._quorum_threshold

    def _check_recovery_quorum(self) -> bool:
        """Check if recovery quorum is reached."""
        if not self._state.is_locked:
            return False  # Not in lockdown

        total = len(self._registered_nodes)
        if total == 0:
            return False

        votes = len(self._recovery_votes)
        return (votes / total) >= self._quorum_threshold

    def _trigger_quorum_lockdown(self) -> None:
        """Trigger lockdown after quorum is reached."""
        self._state.is_locked = True
        self._state.locked_by = "quorum"
        self._state.lock_reason = "Quorum-based lockdown"
        self._state.lock_timestamp = time.time()

        # Clear votes for next round
        self._lockdown_votes.clear()

        # Trigger local lockdown
        if self._local_lockdown:
            self._local_lockdown()

    def _trigger_quorum_recovery(self) -> None:
        """Trigger recovery after quorum is reached."""
        self._state.is_locked = False
        self._state.locked_by = ""
        self._state.lock_reason = ""
        self._state.locked_nodes.clear()

        # Clear votes for next round
        self._recovery_votes.clear()

        # Trigger local recovery
        if self._local_recovery:
            self._local_recovery()

    def register_node(self, node_id: str) -> None:
        """Register a node in the cluster."""
        self._registered_nodes.add(node_id)

    def broadcast_lockdown_vote(self, reason: str) -> bool:
        """
        Broadcast a lockdown vote to all peers.

        Instead of immediately triggering lockdown, this method
        broadcasts a vote. Lockdown is only triggered when quorum
        (2/3 of nodes) is reached.

        Args:
            reason: Reason for requesting lockdown.

        Returns:
            True if broadcast was successful.
        """
        message = LockdownMessage(
            node_id=self.node_id,
            timestamp=time.time(),
            reason=reason,
            message_type=LockdownMessageType.LOCKDOWN_VOTE,
        )
        message.signature = message.compute_signature(self._secret_key)

        # Register own vote
        self._lockdown_votes[self.node_id] = reason
        self._recovery_votes.discard(self.node_id)

        # Check local quorum (might be enough with existing votes)
        if self._check_lockdown_quorum():
            logger.warning("Lockdown quorum reached locally")
            self._trigger_quorum_lockdown()

        return self._broadcast_message(message)

    def broadcast_recovery_vote(self) -> bool:
        """
        Broadcast a recovery vote to all peers.

        Instead of immediately triggering recovery, this method
        broadcasts a vote. Recovery is only triggered when quorum
        (2/3 of nodes) is reached.

        Returns:
            True if broadcast was successful.
        """
        if not self._state.is_locked:
            logger.warning("Cannot vote for recovery: not in lockdown")
            return False

        message = LockdownMessage(
            node_id=self.node_id,
            timestamp=time.time(),
            reason="Recovery vote",
            message_type=LockdownMessageType.RECOVERY_VOTE,
        )
        message.signature = message.compute_signature(self._secret_key)

        # Register own vote
        self._recovery_votes.add(self.node_id)
        if self.node_id in self._lockdown_votes:
            del self._lockdown_votes[self.node_id]

        # Check local quorum (might be enough with existing votes)
        if self._check_recovery_quorum():
            logger.info("Recovery quorum reached locally")
            self._trigger_quorum_recovery()

        return self._broadcast_message(message)

    def get_vote_status(self) -> dict[str, int | float | bool]:
        """Get current vote counts and status."""
        total = len(self._registered_nodes)
        return {
            "total_nodes": total,
            "lockdown_votes": len(self._lockdown_votes),
            "recovery_votes": len(self._recovery_votes),
            "quorum_threshold": self._quorum_threshold,
            "is_locked": self._state.is_locked,
            "lockdown_quorum_reached": (
                len(self._lockdown_votes) / total >= self._quorum_threshold
                if total > 0 else False
            ),
            "recovery_quorum_reached": (
                len(self._recovery_votes) / total >= self._quorum_threshold
                if total > 0 else False
            ),
        }

    def _add_to_history(self, message: LockdownMessage) -> None:
        """Add message to history with size limit."""
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]

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
            f"Broadcasting quarantine report: {len(pending_event_ids)} events, "
            f"block {last_block_index}"
        )

        return self._broadcast_report(report)

    def _broadcast_report(self, report: QuarantineReport) -> bool:
        """Broadcast a QuarantineReport to peers."""
        if not self._zmq_node:
            logger.warning("No ZMQ node configured, cannot broadcast report")
            return False

        try:
            import asyncio
            try:
                asyncio.get_running_loop()
                asyncio.create_task(
                    self._zmq_node.broadcast(report.to_dict())
                )
            except RuntimeError:
                asyncio.run(self._zmq_node.broadcast(report.to_dict()))
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
            report = QuarantineReport.from_dict(data)

            # Verify signature
            if not report.verify_signature(self._secret_key):
                logger.warning(
                    f"Invalid signature on quarantine report from {report.node_id}"
                )
                return None

            # Store report
            self._quarantine_reports[report.node_id] = report

            logger.info(
                f"Received quarantine report from {report.node_id}: "
                f"{report.total_pending} events"
            )
            return report

        except Exception as e:
            logger.error(f"Error processing quarantine report: {e}")
            return None

    def get_quarantine_reports(self) -> dict[str, QuarantineReport]:
        """Get all stored quarantine reports."""
        return self._quarantine_reports.copy()


