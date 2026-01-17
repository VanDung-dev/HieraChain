"""
Unit tests for StateSyncManager.

Tests the "Resurrection" logic - syncing missing blocks from peers.
"""

import time
from dataclasses import dataclass

from hierachain.cluster.state_sync_manager import (
    StateSyncManager,
    SyncRequest,
    SyncResponse,
    SyncStatus,
)


@dataclass
class MockBlock:
    """Mock block for testing."""
    index: int
    hash: str
    previous_hash: str = ""

    def to_dict(self):
        return {
            "index": self.index,
            "hash": self.hash,
            "previous_hash": self.previous_hash,
        }


class MockVerificationResult:
    """Mock verification result."""
    def __init__(self, valid: bool = True, message: str = ""):
        self._valid = valid
        self.message = message

    def is_valid(self):
        return self._valid


class MockBlockVerifier:
    """Mock block verifier for testing."""
    def __init__(self, all_valid: bool = True):
        self.all_valid = all_valid

    def verify_block(self, block, previous_block=None):
        return MockVerificationResult(valid=self.all_valid)


class TestSyncRequest:
    """Tests for SyncRequest dataclass."""

    def test_creation(self):
        """Test creating a SyncRequest."""
        request = SyncRequest(
            node_id="node-1",
            from_index=10,
            to_index=20,
        )
        assert request.node_id == "node-1"
        assert request.from_index == 10
        assert request.to_index == 20

    def test_to_dict(self):
        """Test conversion to dictionary."""
        request = SyncRequest(
            node_id="node-1",
            from_index=5,
            to_index=15,
        )
        data = request.to_dict()

        assert data["msg_type"] == "cluster_lockdown"
        assert data["lockdown_type"] == "sync_request"
        assert data["from_index"] == 5
        assert data["to_index"] == 15

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "node_id": "node-2",
            "from_index": 100,
            "to_index": 200,
            "from_hash": "abc123",
        }
        request = SyncRequest.from_dict(data)

        assert request.node_id == "node-2"
        assert request.from_index == 100
        assert request.to_index == 200
        assert request.from_hash == "abc123"


class TestSyncResponse:
    """Tests for SyncResponse dataclass."""

    def test_creation(self):
        """Test creating a SyncResponse."""
        response = SyncResponse(
            node_id="node-1",
            blocks=[{"index": 1}, {"index": 2}],
            from_index=1,
            to_index=2,
            total_blocks=2,
        )
        assert response.node_id == "node-1"
        assert len(response.blocks) == 2

    def test_to_dict(self):
        """Test conversion to dictionary."""
        response = SyncResponse(
            node_id="node-1",
            blocks=[{"index": 1}],
        )
        data = response.to_dict()

        assert data["msg_type"] == "cluster_lockdown"
        assert data["lockdown_type"] == "sync_response"


class TestStateSyncManager:
    """Tests for StateSyncManager class."""

    def test_init(self):
        """Test initialization."""
        manager = StateSyncManager(node_id="node-1")
        assert manager.node_id == "node-1"
        assert manager.status == SyncStatus.IDLE

    def test_request_gap_fill_invalid_range(self):
        """Test that invalid range is rejected."""
        manager = StateSyncManager(node_id="node-1")

        # from >= to is invalid
        result = manager.request_gap_fill(from_index=20, to_index=10)
        assert not result

        result = manager.request_gap_fill(from_index=10, to_index=10)
        assert not result

    def test_request_gap_fill_no_zmq(self):
        """Test request without ZMQ node fails gracefully."""
        manager = StateSyncManager(node_id="node-1")
        result = manager.request_gap_fill(from_index=0, to_index=10)

        # Should not crash, just fail
        assert not result
        assert manager.status == SyncStatus.FAILED

    def test_receive_blocks(self):
        """Test receiving blocks from peer."""
        manager = StateSyncManager(node_id="node-1")
        manager._status = SyncStatus.REQUESTING
        manager._target_from_index = 0
        manager._target_to_index = 3

        blocks = [MockBlock(1, "hash1"), MockBlock(2, "hash2")]
        accepted = manager.receive_blocks(blocks, "peer-1")

        assert accepted == 2
        assert manager._stats["blocks_received"] == 2


class TestBlockVerification:
    """Tests for block verification during sync."""

    def test_verify_all_valid(self):
        """Test verification when all blocks are valid."""
        verifier = MockBlockVerifier(all_valid=True)
        synced_blocks = []

        def on_complete(blocks):
            synced_blocks.extend(blocks)

        manager = StateSyncManager(
            node_id="node-1",
            block_verifier=verifier,
            on_sync_complete=on_complete,
        )
        manager._status = SyncStatus.REQUESTING
        manager._target_from_index = 0
        manager._target_to_index = 2

        blocks = [MockBlock(1, "hash1"), MockBlock(2, "hash2")]
        manager.receive_blocks(blocks, "peer-1")

        # Should trigger verification and completion
        assert manager.status == SyncStatus.COMPLETE
        assert len(synced_blocks) == 2

    def test_verify_blocks_rejected(self):
        """Test verification when blocks are invalid."""
        verifier = MockBlockVerifier(all_valid=False)
        manager = StateSyncManager(
            node_id="node-1",
            block_verifier=verifier,
        )
        manager._status = SyncStatus.REQUESTING
        manager._target_from_index = 0
        manager._target_to_index = 2

        blocks = [MockBlock(1, "hash1"), MockBlock(2, "hash2")]
        manager.receive_blocks(blocks, "peer-1")

        # Should fail verification
        assert manager.status == SyncStatus.FAILED
        assert manager._stats["blocks_rejected"] == 2

    def test_no_verifier_accepts_all(self):
        """Test that without verifier, all blocks are accepted."""
        synced_blocks = []

        def on_complete(blocks):
            synced_blocks.extend(blocks)

        manager = StateSyncManager(
            node_id="node-1",
            block_verifier=None,
            on_sync_complete=on_complete,
        )
        manager._status = SyncStatus.REQUESTING
        manager._target_from_index = 0
        manager._target_to_index = 2

        blocks = [MockBlock(1, "hash1"), MockBlock(2, "hash2")]
        manager.receive_blocks(blocks, "peer-1")

        assert manager.status == SyncStatus.COMPLETE
        assert len(synced_blocks) == 2


class TestHandleSyncRequest:
    """Tests for handling incoming sync requests."""

    def test_handle_sync_request(self):
        """Test responding to a sync request."""
        manager = StateSyncManager(node_id="node-1")

        def get_blocks(from_idx, to_idx):
            return [MockBlock(i, f"hash{i}") for i in range(from_idx + 1, to_idx + 1)]

        request = SyncRequest(node_id="peer-1", from_index=5, to_index=10)
        response = manager.handle_sync_request(request, get_blocks)

        assert response is not None
        assert response.node_id == "node-1"
        assert len(response.blocks) == 5  # blocks 6-10


class TestSyncReset:
    """Tests for sync state reset."""

    def test_reset(self):
        """Test resetting sync state."""
        manager = StateSyncManager(node_id="node-1")
        manager._status = SyncStatus.FAILED
        manager._received_blocks = [MockBlock(1, "hash")]

        manager.reset()

        assert manager.status == SyncStatus.IDLE
        assert len(manager._received_blocks) == 0

    def test_get_verified_blocks(self):
        """Test getting verified blocks from last sync."""
        manager = StateSyncManager(node_id="node-1")
        manager._verified_blocks = [MockBlock(1, "h1"), MockBlock(2, "h2")]

        verified = manager.get_verified_blocks()
        assert len(verified) == 2
