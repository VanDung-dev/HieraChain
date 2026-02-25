"""
Cluster Manager for HieraChain.

This module provides cluster-wide health tracking and quorum-based
coordination for lockdown and recovery operations.

Features:
- Track health status of all nodes in the cluster
- Quorum-based lockdown voting (2/3 majority required)
- Quorum-based recovery voting
- Cluster-wide health metrics
"""

import time
import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Health status of a cluster node."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class NodeHealthStatus:
    """
    Health status tracking for a cluster node.

    Attributes:
        node_id: Unique identifier of the node.
        address: Network address of the node.
        status: Current health status.
        last_heartbeat: Timestamp of last heartbeat received.
        lockdown_vote: Whether node voted for lockdown.
        recovery_vote: Whether node voted for recovery.
        lockdown_reason: Reason provided for lockdown vote.
    """
    node_id: str
    address: str = ""
    status: NodeStatus = NodeStatus.UNKNOWN
    last_heartbeat: float = 0.0
    lockdown_vote: bool = False
    recovery_vote: bool = False
    lockdown_reason: str = ""

    def is_healthy(self, heartbeat_timeout: float = 30.0) -> bool:
        """Check if node is healthy based on heartbeat."""
        if self.status == NodeStatus.UNHEALTHY:
            return False
        if self.last_heartbeat == 0.0:
            return False
        return (time.time() - self.last_heartbeat) < heartbeat_timeout


@dataclass
class ClusterHealthMetrics:
    """Cluster-wide health metrics."""
    total_nodes: int = 0
    healthy_nodes: int = 0
    unhealthy_nodes: int = 0
    unknown_nodes: int = 0
    lockdown_votes: int = 0
    recovery_votes: int = 0
    is_in_lockdown: bool = False
    quorum_threshold: float = 0.67  # 2/3 majority


class ClusterManager:
    """
    Manages cluster state and health tracking.

    Coordinates quorum-based lockdown and recovery operations
    across the cluster.

    Example:
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")
        
        # Vote for lockdown
        if manager.vote_lockdown("node-1", "High CPU usage"):
            print("Quorum reached - triggering cluster lockdown")
    """

    def __init__(
        self,
        node_id: str,
        quorum_threshold: float = 0.66,  # 2/3 majority - use 0.66 for proper 3-node quorum
        heartbeat_timeout: float = 30.0,
        on_lockdown_quorum: Callable[[], None] | None = None,
        on_recovery_quorum: Callable[[], None] | None = None,
        cluster_secret: str = "",
    ):
        """
        Initialize cluster manager.

        Args:
            node_id: This node's unique identifier.
            quorum_threshold: Fraction of nodes needed for quorum (default 2/3).
            heartbeat_timeout: Seconds before node is considered unhealthy.
            on_lockdown_quorum: Callback when lockdown quorum is reached.
            on_recovery_quorum: Callback when recovery quorum is reached.
            cluster_secret: Shared secret for node authentication.
        """
        self.node_id = node_id
        self.quorum_threshold = quorum_threshold
        self.heartbeat_timeout = heartbeat_timeout
        self._on_lockdown_quorum = on_lockdown_quorum
        self._on_recovery_quorum = on_recovery_quorum
        self.cluster_secret = cluster_secret

        self._nodes: dict[str, NodeHealthStatus] = {}
        self._is_locked_down = False
        self._lock = threading.RLock()

        # Register self as first node
        self.register_node(node_id, "localhost")
        self.update_heartbeat(node_id)

    def register_node(self, node_id: str, address: str, auth_token: str | None = None) -> None:
        """
        Register a node in the cluster.

        Args:
            node_id: Unique identifier of the node.
            address: Network address of the node.
            auth_token: Optional authentication token for the node.
        """
        import re

        # Basic address validation
        if not re.match(r"^([a-zA-Z0-9.-]+)(:\d+)?$", address) and node_id != self.node_id and address != "localhost":
            logger.warning(f"Invalid address format for node {node_id}")
            return

        # Basic auth verification
        if getattr(self, "cluster_secret", "") and node_id != self.node_id:
            if not auth_token or auth_token != self.cluster_secret:
                logger.warning(f"Authentication failed for node {node_id}")
                return

        with self._lock:
            if node_id not in self._nodes:
                self._nodes[node_id] = NodeHealthStatus(
                    node_id=node_id,
                    address=address,
                    status=NodeStatus.UNKNOWN,
                    last_heartbeat=0.0,
                )
                logger.info(f"Registered node {node_id} at {address}")
            else:
                self._nodes[node_id].address = address

    def unregister_node(self, node_id: str) -> None:
        """Remove a node from the cluster."""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                logger.info(f"Unregistered node {node_id}")

    def update_heartbeat(self, node_id: str) -> None:
        """
        Update heartbeat timestamp for a node.

        Args:
            node_id: Node to update.
        """
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].last_heartbeat = time.time()
                self._nodes[node_id].status = NodeStatus.HEALTHY

    def update_status(self, node_id: str, status: NodeStatus) -> None:
        """
        Update health status of a node.

        Args:
            node_id: Node to update.
            status: New health status.
        """
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = status
                if status == NodeStatus.HEALTHY:
                    self._nodes[node_id].last_heartbeat = time.time()

    def get_node_status(self, node_id: str) -> NodeHealthStatus | None:
        """Get health status of a specific node."""
        with self._lock:
            return self._nodes.get(node_id)

    def get_cluster_health(self) -> ClusterHealthMetrics:
        """
        Get cluster-wide health metrics.

        Returns:
            ClusterHealthMetrics with current cluster state.
        """
        with self._lock:
            nodes = list(self._nodes.values())
            timeout = self.heartbeat_timeout

            # Calculate counts using generator expressions to reduce complexity
            healthy = sum(1 for n in nodes if n.is_healthy(timeout))
            unhealthy = sum(1 for n in nodes if not n.is_healthy(timeout) and n.status == NodeStatus.UNHEALTHY)
            unknown = len(nodes) - healthy - unhealthy

            return ClusterHealthMetrics(
                total_nodes=len(nodes),
                healthy_nodes=healthy,
                unhealthy_nodes=unhealthy,
                unknown_nodes=unknown,
                lockdown_votes=sum(1 for n in nodes if n.lockdown_vote),
                recovery_votes=sum(1 for n in nodes if n.recovery_vote),
                is_in_lockdown=self._is_locked_down,
                quorum_threshold=self.quorum_threshold,
            )

    def vote_lockdown(self, node_id: str, reason: str = "") -> bool:
        """
        Register a lockdown vote from a node.

        Args:
            node_id: Node voting for lockdown.
            reason: Reason for lockdown vote.

        Returns:
            True if quorum is reached after this vote.
        """
        with self._lock:
            if node_id not in self._nodes:
                logger.warning(f"Unknown node {node_id} tried to vote for lockdown")
                return False

            self._nodes[node_id].lockdown_vote = True
            self._nodes[node_id].lockdown_reason = reason
            self._nodes[node_id].recovery_vote = False  # Clear recovery vote
            logger.info(f"Node {node_id} voted for lockdown: {reason}")

            return self._check_lockdown_quorum()

    def vote_recovery(self, node_id: str) -> bool:
        """
        Register a recovery vote from a node.

        Args:
            node_id: Node voting for recovery.

        Returns:
            True if quorum is reached after this vote.
        """
        with self._lock:
            if node_id not in self._nodes:
                logger.warning(f"Unknown node {node_id} tried to vote for recovery")
                return False

            self._nodes[node_id].recovery_vote = True
            self._nodes[node_id].lockdown_vote = False  # Clear lockdown vote
            logger.info(f"Node {node_id} voted for recovery")

            return self._check_recovery_quorum()

    def clear_votes(self) -> None:
        """Clear all lockdown and recovery votes."""
        with self._lock:
            for node in self._nodes.values():
                node.lockdown_vote = False
                node.recovery_vote = False
                node.lockdown_reason = ""

    def _check_lockdown_quorum(self) -> bool:
        """
        Check if lockdown quorum is reached.

        Returns:
            True if quorum is reached and lockdown should be triggered.
        """
        total_nodes = len(self._nodes)
        if self._is_locked_down or total_nodes == 0:
            return False

        lockdown_votes = sum(1 for n in self._nodes.values() if n.lockdown_vote)
        vote_ratio = lockdown_votes / total_nodes

        if vote_ratio < self.quorum_threshold:
            logger.debug(f"Lockdown votes: {lockdown_votes}/{total_nodes} ({vote_ratio:.1%} < {self.quorum_threshold:.1%})")
            return False

        self._is_locked_down = True
        logger.warning(f"Lockdown quorum reached: {lockdown_votes}/{total_nodes} ({vote_ratio:.1%} >= {self.quorum_threshold:.1%})")
        
        self._clear_lockdown_votes()
        if self._on_lockdown_quorum:
            try:
                self._on_lockdown_quorum()
            except Exception as e:
                logger.error(f"Error in lockdown callback: {e}")
        return True

    def _check_recovery_quorum(self) -> bool:
        """
        Check if recovery quorum is reached.

        Returns:
            True if quorum is reached and recovery should be triggered.
        """
        total_nodes = len(self._nodes)
        if not self._is_locked_down or total_nodes == 0:
            return False

        recovery_votes = sum(1 for n in self._nodes.values() if n.recovery_vote)
        vote_ratio = recovery_votes / total_nodes

        if vote_ratio < self.quorum_threshold:
            logger.debug(f"Recovery votes: {recovery_votes}/{total_nodes} ({vote_ratio:.1%} < {self.quorum_threshold:.1%})")
            return False

        self._is_locked_down = False
        logger.info(f"Recovery quorum reached: {recovery_votes}/{total_nodes} ({vote_ratio:.1%} >= {self.quorum_threshold:.1%})")
        
        self._clear_recovery_votes()
        if self._on_recovery_quorum:
            try:
                self._on_recovery_quorum()
            except Exception as e:
                logger.error(f"Error in recovery callback: {e}")
        return True

    def _clear_lockdown_votes(self) -> None:
        """Clear lockdown votes after quorum is reached."""
        for node in self._nodes.values():
            node.lockdown_vote = False
            node.lockdown_reason = ""

    def _clear_recovery_votes(self) -> None:
        """Clear recovery votes after quorum is reached."""
        for node in self._nodes.values():
            node.recovery_vote = False

    @property
    def is_locked_down(self) -> bool:
        """Check if cluster is in lockdown state."""
        with self._lock:
            return self._is_locked_down

    @property
    def node_count(self) -> int:
        """Get total number of registered nodes."""
        with self._lock:
            return len(self._nodes)

    def get_all_nodes(self) -> list[NodeHealthStatus]:
        """Get list of all registered nodes."""
        with self._lock:
            return list(self._nodes.values())
