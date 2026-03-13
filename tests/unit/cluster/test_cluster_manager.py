"""
Unit tests for ClusterManager.
"""

import time

from hierachain.cluster import (
    ClusterManager,
    NodeHealthStatus,
    NodeStatus,
    ClusterHealthMetrics,
)


class TestNodeHealthStatus:
    """Tests for NodeHealthStatus dataclass."""

    def test_node_health_status_creation(self):
        """Test creating a NodeHealthStatus instance."""
        status = NodeHealthStatus(
            node_id="node-1",
            address="192.168.1.1:5000",
            status=NodeStatus.HEALTHY,
            last_heartbeat=time.time(),
        )
        assert status.node_id == "node-1"
        assert status.status == NodeStatus.HEALTHY
        assert not status.lockdown_vote
        assert not status.recovery_vote

    def test_is_healthy_with_recent_heartbeat(self):
        """Test is_healthy returns True with recent heartbeat."""
        status = NodeHealthStatus(
            node_id="node-1",
            address="localhost",
            status=NodeStatus.HEALTHY,
            last_heartbeat=time.time(),
        )
        assert status.is_healthy(heartbeat_timeout=30.0)

    def test_is_healthy_with_stale_heartbeat(self):
        """Test is_healthy returns False with stale heartbeat."""
        status = NodeHealthStatus(
            node_id="node-1",
            address="localhost",
            status=NodeStatus.HEALTHY,
            last_heartbeat=time.time() - 60.0,  # 60 seconds ago
        )
        assert not status.is_healthy(heartbeat_timeout=30.0)

    def test_is_healthy_with_unhealthy_status(self):
        """Test is_healthy returns False when status is UNHEALTHY."""
        status = NodeHealthStatus(
            node_id="node-1",
            address="localhost",
            status=NodeStatus.UNHEALTHY,
            last_heartbeat=time.time(),
        )
        assert not status.is_healthy()


class TestClusterManager:
    """Tests for ClusterManager class."""

    def test_init_registers_self(self):
        """Test that initialization registers the node itself."""
        manager = ClusterManager(node_id="node-1")
        assert manager.node_count == 1
        assert manager.get_node_status("node-1") is not None

    def test_register_node(self):
        """Test registering new nodes."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")

        assert manager.node_count == 3
        assert manager.get_node_status("node-2") is not None
        assert manager.get_node_status("node-3") is not None

    def test_unregister_node(self):
        """Test unregistering nodes."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")

        assert manager.node_count == 2
        manager.unregister_node("node-2")
        assert manager.node_count == 1
        assert manager.get_node_status("node-2") is None

    def test_update_heartbeat(self):
        """Test updating heartbeat."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")

        manager.update_heartbeat("node-2")

        status = manager.get_node_status("node-2")
        assert status is not None
        assert status.status == NodeStatus.HEALTHY
        assert status.last_heartbeat > 0

    def test_update_status(self):
        """Test updating node status."""
        manager = ClusterManager(node_id="node-1")
        manager.update_status("node-1", NodeStatus.UNHEALTHY)

        status = manager.get_node_status("node-1")
        assert status is not None
        assert status.status == NodeStatus.UNHEALTHY

    def test_get_cluster_health(self):
        """Test getting cluster health metrics."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")

        # Update heartbeats for all nodes
        manager.update_heartbeat("node-1")
        manager.update_heartbeat("node-2")
        manager.update_heartbeat("node-3")

        metrics = manager.get_cluster_health()
        assert isinstance(metrics, ClusterHealthMetrics)
        assert metrics.total_nodes == 3
        assert metrics.healthy_nodes == 3
        assert metrics.unhealthy_nodes == 0
        assert not metrics.is_in_lockdown


class TestQuorumBasedLockdown:
    """Tests for quorum-based lockdown functionality."""

    def test_lockdown_vote_not_enough(self):
        """Test that single vote doesn't trigger lockdown."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")

        # 1 out of 3 = 33% < 66% threshold
        result = manager.vote_lockdown("node-1", "High CPU")
        assert not result
        assert not manager.is_locked_down

    def test_lockdown_quorum_3_nodes(self):
        """Test lockdown quorum with 3 nodes (needs 2 votes)."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")

        # 1st vote: 1/3 = 33%
        result1 = manager.vote_lockdown("node-1", "High CPU")
        assert not result1
        assert not manager.is_locked_down

        # 2nd vote: 2/3 = 67% >= 66% threshold
        result2 = manager.vote_lockdown("node-2", "Memory pressure")
        assert result2
        assert manager.is_locked_down

    def test_lockdown_quorum_5_nodes(self):
        """Test lockdown quorum with 5 nodes (needs 4 votes)."""
        manager = ClusterManager(node_id="node-1")
        for i in range(2, 6):
            manager.register_node(f"node-{i}", f"192.168.1.{i}:5000")

        # Vote 1: 1/5 = 20%
        assert not manager.vote_lockdown("node-1", "reason")

        # Vote 2: 2/5 = 40%
        assert not manager.vote_lockdown("node-2", "reason")

        # Vote 3: 3/5 = 60%
        assert not manager.vote_lockdown("node-3", "reason")

        # Vote 4: 4/5 = 80% >= 66%
        assert manager.vote_lockdown("node-4", "reason")
        assert manager.is_locked_down


class TestQuorumBasedRecovery:
    """Tests for quorum-based recovery functionality."""

    def test_recovery_vote_not_in_lockdown(self):
        """Test that recovery vote fails when not in lockdown."""
        manager = ClusterManager(node_id="node-1")
        result = manager.vote_recovery("node-1")
        assert not result

    def test_recovery_quorum_3_nodes(self):
        """Test recovery quorum with 3 nodes (needs 2 votes)."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")

        # First, trigger lockdown
        manager.vote_lockdown("node-1", "reason")
        manager.vote_lockdown("node-2", "reason")
        assert manager.is_locked_down

        # 1st recovery vote: 1/3 = 33%
        result1 = manager.vote_recovery("node-1")
        assert not result1
        assert manager.is_locked_down

        # 2nd recovery vote: 2/3 = 67% >= 66%
        result2 = manager.vote_recovery("node-2")
        assert result2
        assert not manager.is_locked_down

    def test_lockdown_clears_recovery_vote(self):
        """Test that lockdown vote clears any recovery vote from same node."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")

        # Trigger lockdown
        manager.vote_lockdown("node-1", "reason")
        manager.vote_lockdown("node-2", "reason")

        # Start recovery voting
        manager.vote_recovery("node-1")

        # Same node switches to lockdown vote
        manager._nodes["node-1"].lockdown_vote = True
        manager._nodes["node-1"].recovery_vote = False

        # Verify vote was updated
        status = manager.get_node_status("node-1")
        assert status.lockdown_vote
        assert not status.recovery_vote


class TestClusterManagerCallbacks:
    """Tests for callback functionality."""

    def test_lockdown_callback(self):
        """Test that lockdown callback is triggered on quorum."""
        callback_called = []

        def on_lockdown():
            callback_called.append(True)

        manager = ClusterManager(
            node_id="node-1",
            on_lockdown_quorum=on_lockdown,
        )
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")

        manager.vote_lockdown("node-1", "reason")
        assert len(callback_called) == 0

        manager.vote_lockdown("node-2", "reason")
        assert len(callback_called) == 1

    def test_recovery_callback(self):
        """Test that recovery callback is triggered on quorum."""
        recovery_called = []

        def on_recovery():
            recovery_called.append(True)

        manager = ClusterManager(
            node_id="node-1",
            on_recovery_quorum=on_recovery,
        )
        manager.register_node("node-2", "192.168.1.2:5000")
        manager.register_node("node-3", "192.168.1.3:5000")

        # Trigger lockdown first
        manager.vote_lockdown("node-1", "reason")
        manager.vote_lockdown("node-2", "reason")

        # Now vote for recovery
        manager.vote_recovery("node-1")
        assert len(recovery_called) == 0

        manager.vote_recovery("node-2")
        assert len(recovery_called) == 1


class TestClearVotes:
    """Tests for vote clearing functionality."""

    def test_clear_votes(self):
        """Test clearing all votes."""
        manager = ClusterManager(node_id="node-1")
        manager.register_node("node-2", "192.168.1.2:5000")

        manager.vote_lockdown("node-1", "reason")
        metrics = manager.get_cluster_health()
        assert metrics.lockdown_votes == 1

        manager.clear_votes()
        metrics = manager.get_cluster_health()
        assert metrics.lockdown_votes == 0
        assert metrics.recovery_votes == 0
