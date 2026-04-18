"""
State Synchronization Manager for HieraChain.

Implements "Resurrection" logic - syncing missing blocks from peers
after recovery from lockdown or flush.

Features:
- Request gap-fill blocks from peers
- Verify received blocks using BlockVerifier
- Merge verified blocks into local chain
"""

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, cast

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of synchronization operation."""
    IDLE = "idle"
    REQUESTING = "requesting"
    RECEIVING = "receiving"
    VERIFYING = "verifying"
    MERGING = "merging"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class SyncRequest:
    """Request for gap-fill blocks from a peer."""
    node_id: str
    from_index: int
    to_index: int
    from_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "msg_type": "cluster_lockdown",
            "lockdown_type": "sync_request",
            "node_id": self.node_id,
            "from_index": self.from_index,
            "to_index": self.to_index,
            "from_hash": self.from_hash,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncRequest":
        """Create from dictionary."""
        return cls(
            node_id=data.get("node_id", "unknown"),
            from_index=data.get("from_index", 0),
            to_index=data.get("to_index", 0),
            from_hash=data.get("from_hash", ""),
            timestamp=data.get("timestamp", 0.0),
        )


@dataclass
class SyncResponse:
    """Response with blocks for gap-fill."""
    node_id: str
    blocks: list[dict[str, Any]] = field(default_factory=list)
    from_index: int = 0
    to_index: int = 0
    total_blocks: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "msg_type": "cluster_lockdown",
            "lockdown_type": "sync_response",
            "node_id": self.node_id,
            "blocks": self.blocks,
            "from_index": self.from_index,
            "to_index": self.to_index,
            "total_blocks": self.total_blocks,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncResponse":
        """Create from dictionary."""
        return cls(
            node_id=data.get("node_id", "unknown"),
            blocks=data.get("blocks", []),
            from_index=data.get("from_index", 0),
            to_index=data.get("to_index", 0),
            total_blocks=data.get("total_blocks", 0),
            timestamp=data.get("timestamp", 0.0),
        )


class StateSyncManager:
    """
    Manages state synchronization after recovery (Resurrection).

    Requests missing blocks from peers, verifies them using BlockVerifier,
    and merges them into the local chain.
    """

    def __init__(
        self,
        node_id: str,
        block_verifier: Any = None,
        zmq_node: Any = None,
        on_sync_complete: Callable[[list[Any]], None] | None = None,
        max_blocks_per_request: int = 100,
    ):
        """
        Initialize StateSyncManager.

        Args:
            node_id: ID of this node.
            block_verifier: BlockVerifier instance for verification.
            zmq_node: ZmqNode for P2P communication.
            on_sync_complete: Callback when sync completes with blocks.
            max_blocks_per_request: Maximum blocks to request at once.
        """
        self.node_id = node_id
        self._block_verifier = block_verifier
        self._zmq_node = zmq_node
        self._on_sync_complete = on_sync_complete
        self._max_blocks = max_blocks_per_request

        self._status = SyncStatus.IDLE
        self._pending_requests: dict[str, SyncRequest] = {}
        self._received_blocks: list[Any] = []
        self._verified_blocks: list[Any] = []

        # Sync tracking
        self._target_from_index = 0
        self._target_to_index = 0
        self._last_known_hash = ""

        # Statistics
        self._stats = {
            "sync_attempts": 0,
            "blocks_received": 0,
            "blocks_verified": 0,
            "blocks_rejected": 0,
            "sync_completed": 0,
            "sync_failed": 0,
        }

    @property
    def status(self) -> SyncStatus:
        """Get current sync status."""
        return self._status

    @property
    def stats(self) -> dict[str, int]:
        """Get sync statistics."""
        return self._stats.copy()

    def request_gap_fill(
        self,
        from_index: int,
        to_index: int,
        from_hash: str = "",
    ) -> bool:
        """
        Request blocks to fill a gap in the local chain.

        Args:
            from_index: Starting block index (exclusive).
            to_index: Ending block index (inclusive).
            from_hash: Hash of the last known block (for verification).

        Returns:
            True if request was sent successfully.
        """
        if self._status not in (SyncStatus.IDLE, SyncStatus.COMPLETE):
            logger.warning(f"Sync already in progress: {self._status.value}")
            return False

        if from_index >= to_index:
            logger.warning(f"Invalid range: {from_index} >= {to_index}")
            return False

        self._status = SyncStatus.REQUESTING
        self._target_from_index = from_index
        self._target_to_index = to_index
        self._last_known_hash = from_hash
        self._received_blocks.clear()
        self._verified_blocks.clear()
        self._stats["sync_attempts"] += 1

        request = SyncRequest(
            node_id=self.node_id,
            from_index=from_index,
            to_index=min(to_index, from_index + self._max_blocks),
            from_hash=from_hash,
        )

        logger.info(f"Requesting gap-fill: blocks {from_index} to {to_index}")

        return self._broadcast_request(request)

    def _broadcast_request(self, request: SyncRequest) -> bool:
        """Broadcast sync request to peers."""
        zmq_node = self._zmq_node
        if zmq_node is None:
            logger.warning("No ZMQ node configured, cannot request sync")
            self._status = SyncStatus.FAILED
            return False

        # Cast to Any to satisfy the type checker after null check
        safe_node = cast(Any, zmq_node)

        try:
            import asyncio
            try:
                asyncio.get_running_loop()
                asyncio.create_task(
                    safe_node.broadcast(request.to_dict())
                )
            except RuntimeError:
                asyncio.run(safe_node.broadcast(request.to_dict()))

            self._pending_requests[request.node_id] = request
            return True
        except Exception as e:
            logger.error("Failed to broadcast sync request: %s", e)
            self._status = SyncStatus.FAILED
            return False

    def receive_blocks(
        self,
        blocks: list[Any],
        peer_id: str,
    ) -> int:
        """
        Receive blocks from a peer response.

        Args:
            blocks: List of block objects or dicts.
            peer_id: ID of the peer that sent the blocks.

        Returns:
            Number of blocks accepted.
        """
        if self._status not in (SyncStatus.REQUESTING, SyncStatus.RECEIVING):
            logger.warning("Not expecting blocks, status: %s", self._status)
            return 0

        self._status = SyncStatus.RECEIVING
        accepted = 0

        for block in blocks:
            self._received_blocks.append(block)
            self._stats["blocks_received"] += 1
            accepted += 1

        logger.info("Received %s blocks from %s", accepted, peer_id)

        # Check if we have all blocks
        if (
            len(self._received_blocks) >=
            (self._target_to_index - self._target_from_index)
        ):
            self._verify_and_merge()

        return accepted

    def _verify_and_merge(self) -> bool:
        """Verify received blocks and merge into chain."""
        self._status = SyncStatus.VERIFYING

        if not self._block_verifier:
            logger.warning("No block verifier, accepting blocks without verification")
            self._verified_blocks = self._received_blocks.copy()
            return self._complete_sync()

        self._verified_blocks = self._verify_received_blocks()

        if not self._verified_blocks:
            logger.error("No blocks passed verification")
            self._status = SyncStatus.FAILED
            self._stats["sync_failed"] += 1
            return False

        return self._complete_sync()

    def _verify_received_blocks(self) -> list[Any]:
        """Iterate and verify all received blocks."""
        verified = []
        previous_block = None

        for block in self._received_blocks:
            if self._verify_single_block(block, previous_block):
                verified.append(block)
                previous_block = block
        
        return verified

    def _verify_single_block(self, block: Any, previous_block: Any | None) -> bool:
        """Verify a single block and update statistics."""
        verifier = self._block_verifier
        if verifier is None:
            return True

        # Cast to Any to satisfy the type checker after null check
        safe_verifier = cast(Any, verifier)

        try:
            result = safe_verifier.verify_block(block, previous_block)
            if result.is_valid():
                self._stats["blocks_verified"] += 1
                return True
            
            logger.warning("Block verification failed: %s", result.message)
            self._stats["blocks_rejected"] += 1
        except Exception as e:
            logger.error("Block verification error: %s", e)
            self._stats["blocks_rejected"] += 1
            
        return False

    def _complete_sync(self) -> bool:
        """Complete sync by merging verified blocks."""
        self._status = SyncStatus.MERGING

        if self._on_sync_complete:
            try:
                self._on_sync_complete(self._verified_blocks)
            except Exception as e:
                logger.error("Sync complete callback failed: %s", e)
                self._status = SyncStatus.FAILED
                self._stats["sync_failed"] += 1
                return False

        self._status = SyncStatus.COMPLETE
        self._stats["sync_completed"] += 1

        logger.info(
            "Sync completed: %s blocks merged",
            len(self._verified_blocks),
        )
        return True

    def handle_sync_request(
        self,
        request: SyncRequest,
        get_blocks: Callable[[int, int], list[Any]],
    ) -> SyncResponse | None:
        """
        Handle incoming sync request from a peer.

        Args:
            request: The sync request from peer.
            get_blocks: Callback to get blocks by index range.

        Returns:
            SyncResponse with requested blocks, or None on error.
        """
        try:
            blocks = get_blocks(request.from_index, request.to_index)

            response = SyncResponse(
                node_id=self.node_id,
                blocks=[b.to_dict() if hasattr(b, "to_dict") else b for b in blocks],
                from_index=request.from_index,
                to_index=request.to_index,
                total_blocks=len(blocks),
            )

            logger.info(
                "Responding to sync request from %s: %s blocks",
                request.node_id,
                len(blocks),
            )
            return response

        except Exception as e:
            logger.error("Error handling sync request: %s", e)
            return None

    def reset(self) -> None:
        """Reset sync state."""
        self._status = SyncStatus.IDLE
        self._pending_requests.clear()
        self._received_blocks.clear()
        self._verified_blocks.clear()
        self._target_from_index = 0
        self._target_to_index = 0

    def get_verified_blocks(self) -> list[Any]:
        """Get list of verified blocks from last sync."""
        return self._verified_blocks.copy()
