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
import json
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
        secret_key: str = "default_secret_key",
    ):
        """
        Initialize cluster lockdown manager.

        Args:
            node_id: This node's unique identifier.
            zmq_node: ZmqNode instance for P2P messaging (optional).
            local_lockdown_callback: Function to call for local lockdown.
            secret_key: Shared secret for message signing.
        """
        self.node_id = node_id
        self._zmq_node = zmq_node
        self._local_lockdown = local_lockdown_callback
        self._secret_key = secret_key
        self._state = ClusterState()
        self._message_history: list[LockdownMessage] = []
        self._max_history = 100

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
                loop = asyncio.get_running_loop()
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

        if message.message_type == LockdownMessageType.LOCKDOWN:
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

        elif message.message_type == LockdownMessageType.RECOVERY:
            if self._state.locked_by == message.node_id:
                self._state.is_locked = False
                self._state.locked_by = ""
                self._state.lock_reason = ""
                self._state.locked_nodes.clear()
                logger.info(f"Cluster recovery received from {message.node_id}")

    def _add_to_history(self, message: LockdownMessage) -> None:
        """Add message to history with size limit."""
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]

    def get_history(self) -> list[dict]:
        """Get message history as list of dicts."""
        return [m.to_dict() for m in self._message_history]
