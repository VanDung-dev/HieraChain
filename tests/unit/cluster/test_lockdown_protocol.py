"""
Unit tests for ClusterLockdownManager.

Tests the quorum-based lockdown and recovery voting functionality.
"""

import time

from hierachain.cluster.lockdown_protocol import (
    ClusterLockdownManager,
    ClusterState,
    LockdownMessage,
    LockdownMessageType,
)


class TestLockdownMessage:
    """Tests for LockdownMessage dataclass."""

    def test_message_creation(self):
        """Test creating a LockdownMessage."""
        message = LockdownMessage(
            node_id="node-1",
            timestamp=time.time(),
            reason="High CPU usage",
            message_type=LockdownMessageType.LOCKDOWN,
        )
        assert message.node_id == "node-1"
        assert message.message_type == LockdownMessageType.LOCKDOWN

    def test_message_to_dict(self):
        """Test conversion to dictionary."""
        message = LockdownMessage(
            node_id="node-1",
            timestamp=1234567890.0,
            reason="Test reason",
            message_type=LockdownMessageType.LOCKDOWN_VOTE,
        )
        data = message.to_dict()

        assert data["msg_type"] == "cluster_lockdown"
        assert data["node_id"] == "node-1"
        assert data["lockdown_type"] == "lockdown_vote"

    def test_message_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "node_id": "node-2",
            "timestamp": 1234567890.0,
            "reason": "Memory pressure",
            "lockdown_type": "recovery_vote",
            "signature": "abc123",
        }
        message = LockdownMessage.from_dict(data)

        assert message.node_id == "node-2"
        assert message.message_type == LockdownMessageType.RECOVERY_VOTE
        assert message.signature == "abc123"

    def test_signature_computation(self):
        """Test signature computation and verification."""
        message = LockdownMessage(
            node_id="node-1",
            timestamp=1234567890.0,
            reason="Test",
            message_type=LockdownMessageType.LOCKDOWN,
        )
        secret = "my_secret_key"
        signature = message.compute_signature(secret)
        message.signature = signature

        assert message.verify_signature(secret)
        assert not message.verify_signature("wrong_key")


class TestClusterLockdownManager:
    """Tests for ClusterLockdownManager class."""

    def test_init(self):
        """Test initialization."""
        manager = ClusterLockdownManager(node_id="node-1")
        assert manager.node_id == "node-1"
        assert not manager.is_cluster_locked

    def test_cluster_state(self):
        """Test cluster state access."""
        manager = ClusterLockdownManager(node_id="node-1")
        state = manager.cluster_state

        assert isinstance(state, ClusterState)
        assert not state.is_locked

    def test_register_node(self):
        """Test node registration."""
        manager = ClusterLockdownManager(node_id="node-1")
        manager.register_node("node-2")
        manager.register_node("node-3")

        vote_status = manager.get_vote_status()
        assert vote_status["total_nodes"] == 3


class TestQuorumLockdownVoting:
    """Tests for quorum-based lockdown voting."""

    def test_broadcast_lockdown_vote_single_node(self):
        """Test lockdown vote with single node triggers immediately."""
        lockdown_triggered = []

        def on_lockdown():
            lockdown_triggered.append(True)

        manager = ClusterLockdownManager(
            node_id="node-1",
            local_lockdown_callback=on_lockdown,
        )

        # Single node = 1/1 = 100% >= 67%
        manager.broadcast_lockdown_vote("High CPU")

        assert manager.is_cluster_locked
        assert len(lockdown_triggered) == 1

    def test_lockdown_vote_3_nodes(self):
        """Test lockdown vote with 3 nodes needs 2 votes."""
        lockdown_triggered = []

        def on_lockdown():
            lockdown_triggered.append(True)

        manager = ClusterLockdownManager(
            node_id="node-1",
            local_lockdown_callback=on_lockdown,
        )
        manager.register_node("node-2")
        manager.register_node("node-3")

        # 1st vote from self: 1/3 = 33%
        manager.broadcast_lockdown_vote("High CPU")
        assert not manager.is_cluster_locked

        # Simulate receiving vote from node-2
        vote_message = LockdownMessage(
            node_id="node-2",
            timestamp=time.time(),
            reason="Memory pressure",
            message_type=LockdownMessageType.LOCKDOWN_VOTE,
        )
        vote_message.signature = vote_message.compute_signature("default_secret_key")
        manager._handle_lockdown_vote(vote_message)

        # 2/3 = 67% >= 66%
        assert manager.is_cluster_locked
        assert len(lockdown_triggered) == 1

    def test_get_vote_status(self):
        """Test getting vote status."""
        manager = ClusterLockdownManager(node_id="node-1")
        manager.register_node("node-2")
        manager.register_node("node-3")

        status = manager.get_vote_status()
        assert status["total_nodes"] == 3
        assert status["lockdown_votes"] == 0
        assert status["recovery_votes"] == 0
        assert status["quorum_threshold"] == 0.66
        assert not status["is_locked"]


class TestQuorumRecoveryVoting:
    """Tests for quorum-based recovery voting."""

    def test_recovery_vote_not_in_lockdown(self):
        """Test that recovery vote fails when not in lockdown."""
        manager = ClusterLockdownManager(node_id="node-1")
        result = manager.broadcast_recovery_vote()
        assert not result

    def test_recovery_vote_3_nodes(self):
        """Test recovery vote with 3 nodes needs 2 votes."""
        recovery_triggered = []

        def on_recovery():
            recovery_triggered.append(True)

        manager = ClusterLockdownManager(
            node_id="node-1",
            local_recovery_callback=on_recovery,
        )
        manager.register_node("node-2")
        manager.register_node("node-3")

        # First trigger lockdown
        manager.broadcast_lockdown_vote("reason")
        # Simulate node-2 vote
        vote_message = LockdownMessage(
            node_id="node-2",
            timestamp=time.time(),
            reason="reason",
            message_type=LockdownMessageType.LOCKDOWN_VOTE,
        )
        vote_message.signature = vote_message.compute_signature("default_secret_key")
        manager._handle_lockdown_vote(vote_message)
        assert manager.is_cluster_locked

        # Now vote for recovery - broadcast returns False without ZMQ but state updates
        manager.broadcast_recovery_vote()
        # Still locked because only 1/3 votes
        assert manager.is_cluster_locked

        # Simulate node-2 recovery vote
        recovery_message = LockdownMessage(
            node_id="node-2",
            timestamp=time.time(),
            reason="Recovery",
            message_type=LockdownMessageType.RECOVERY_VOTE,
        )
        recovery_message.signature = recovery_message.compute_signature(
            "default_secret_key"
        )
        manager._handle_recovery_vote(recovery_message)

        # 2/3 = 67% >= 66%
        assert not manager.is_cluster_locked
        assert len(recovery_triggered) == 1


class TestMessageHistory:
    """Tests for message history functionality."""

    def test_get_history(self):
        """Test getting message history from internal method."""
        manager = ClusterLockdownManager(node_id="node-1")

        # Add a message directly to history
        message = LockdownMessage(
            node_id="node-1",
            timestamp=time.time(),
            reason="Test reason",
            message_type=LockdownMessageType.LOCKDOWN_VOTE,
        )
        manager._add_to_history(message)

        history = manager.get_history()
        assert len(history) >= 1

    def test_history_limit(self):
        """Test that history respects max limit."""
        manager = ClusterLockdownManager(node_id="node-1")

        # Add many messages
        for i in range(150):
            message = LockdownMessage(
                node_id=f"node-{i}",
                timestamp=time.time(),
                reason=f"Reason {i}",
                message_type=LockdownMessageType.HEARTBEAT,
            )
            manager._add_to_history(message)

        history = manager.get_history()
        assert len(history) <= 100  # Default max is 100


class TestDirectLockdownBroadcast:
    """Tests for direct lockdown (non-voting) functionality."""

    def test_broadcast_lockdown_direct(self):
        """Test direct lockdown broadcast (legacy behavior)."""
        lockdown_triggered = []

        def on_lockdown():
            lockdown_triggered.append(True)

        manager = ClusterLockdownManager(
            node_id="node-1",
            local_lockdown_callback=on_lockdown,
        )

        # broadcast_lockdown returns False without ZMQ, but state changes
        manager.broadcast_lockdown("Emergency")
        assert manager.is_cluster_locked
        assert len(lockdown_triggered) == 1

    def test_broadcast_recovery_direct(self):
        """Test direct recovery broadcast."""
        recovery_triggered = []

        def on_recovery():
            recovery_triggered.append(True)

        manager = ClusterLockdownManager(
            node_id="node-1",
            local_recovery_callback=on_recovery,
        )

        # First lockdown
        manager.broadcast_lockdown("Emergency")
        assert manager.is_cluster_locked

        # Then recover - state changes even without ZMQ
        manager.broadcast_recovery()
        assert not manager.is_cluster_locked

    def test_broadcast_recovery_not_initiator(self):
        """Test that only initiator can broadcast recovery."""
        manager = ClusterLockdownManager(node_id="node-1")

        # Simulate lockdown from another node
        manager._state.is_locked = True
        manager._state.locked_by = "node-2"

        result = manager.broadcast_recovery()
        assert not result  # Should fail
        assert manager.is_cluster_locked  # Still locked
