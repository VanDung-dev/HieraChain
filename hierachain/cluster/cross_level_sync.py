"""
Cross-Level State Synchronization Manager for HieraChain.

This module implements hierarchical state sync between MainChain and Sub-chains,
enabling gap-fill data sync with proof verification across hierarchy levels.

Features:
- MainChain → Sub-chain state sync
- Sub-chain → MainChain proof-based sync
- Cross-level state verification
- Sync conflict resolution
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CrossLevelSyncStatus(Enum):
    """Status of cross-level synchronization."""
    IDLE = "idle"
    SYNCING_DOWN = "syncing_down"  # MainChain -> SubChain
    SYNCING_UP = "syncing_up"  # SubChain -> MainChain
    VERIFYING = "verifying"
    RESOLVING_CONFLICT = "resolving_conflict"
    COMPLETE = "complete"
    FAILED = "failed"


class SyncDirection(Enum):
    """Direction of sync operation."""
    MAINCHAIN_TO_SUBCHAIN = "mainchain_to_subchain"
    SUBCHAIN_TO_MAINCHAIN = "subchain_to_mainchain"
    BIDIRECTIONAL = "bidirectional"


class ConflictResolutionStrategy(Enum):
    """Strategy for resolving sync conflicts."""
    MAINCHAIN_WINS = "mainchain_wins"
    SUBCHAIN_WINS = "subchain_wins"
    LATEST_TIMESTAMP = "latest_timestamp"
    MANUAL = "manual"


@dataclass
class SyncConflict:
    """Represents a conflict during cross-level sync."""
    conflict_id: str
    source_chain: str
    target_chain: str
    block_index: int
    source_hash: str
    target_hash: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "source_chain": self.source_chain,
            "target_chain": self.target_chain,
            "block_index": self.block_index,
            "source_hash": self.source_hash,
            "target_hash": self.target_hash,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class CrossLevelSyncRequest:
    """Request for cross-level state sync."""
    request_id: str
    source_chain_id: str
    target_chain_id: str
    direction: SyncDirection
    from_block_index: int
    to_block_index: int
    proof_required: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "source_chain_id": self.source_chain_id,
            "target_chain_id": self.target_chain_id,
            "direction": self.direction.value,
            "from_block_index": self.from_block_index,
            "to_block_index": self.to_block_index,
            "proof_required": self.proof_required,
            "timestamp": self.timestamp,
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    blocks_synced: int = 0
    conflicts_found: int = 0
    conflicts_resolved: int = 0
    error_message: str = ""
    duration_seconds: float = 0.0
    state_root_before: str = ""
    state_root_after: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "blocks_synced": self.blocks_synced,
            "conflicts_found": self.conflicts_found,
            "conflicts_resolved": self.conflicts_resolved,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "state_root_before": self.state_root_before,
            "state_root_after": self.state_root_after,
        }

def _get_state_root(chain: Any) -> str:
    """Get state root from chain."""
    if hasattr(chain, "get_state_root"):
        return chain.get_state_root()
    if hasattr(chain, "blockchain"):
        blocks = chain.blockchain.get_chain()
        if blocks:
            last_block = blocks[-1]
            if hasattr(last_block, "hash"):
                return last_block.hash
    return hashlib.sha256(str(time.time()).encode()).hexdigest()


def _get_chain_height(chain: Any) -> int:
    """Get current chain height."""
    if hasattr(chain, "get_block_count"):
        return chain.get_block_count()
    if hasattr(chain, "blockchain"):
        return len(chain.blockchain.get_chain())
    return 0


def _get_blocks(chain: Any, from_idx: int, to_idx: int) -> list[Any]:
    """Get blocks from chain."""
    if hasattr(chain, "get_blocks"):
        return chain.get_blocks(from_idx, to_idx)
    if hasattr(chain, "blockchain"):
        all_blocks = chain.blockchain.get_chain()
        return all_blocks[from_idx:to_idx]
    return []


def _generate_proof(chain: Any, block_height: int) -> bytes:
    """Generate proof for chain state."""
    if hasattr(chain, "generate_proof"):
        return chain.generate_proof(block_height)
    # Mock proof generation
    data = f"{chain}:{block_height}:{time.time()}"
    return hashlib.sha256(data.encode()).digest()


def _apply_block_to_chain(chain: Any, block: Any) -> bool:
    """Apply a block to chain."""
    try:
        if hasattr(chain, "add_block"):
            return chain.add_block(block)
        return True
    except Exception as e:
        logger.error(f"Failed to apply block: {e}")
        return False


def _verify_anchor_exists(mainchain: Any, subchain_id: str, state_root: str) -> bool:
    """Verify that an anchor exists in MainChain."""
    if hasattr(mainchain, "get_anchor"):
        anchor = mainchain.get_anchor(subchain_id)
        if anchor and anchor.get("state_root") == state_root:
            return True
    return False


def _check_conflict(target_chain: Any, block: Any) -> SyncConflict | None:
    """Check for conflicts when applying block."""
    if not hasattr(block, "index"):
        return None

    target_blocks = _get_blocks(target_chain, block.index, block.index + 1)
    if not target_blocks:
        return None

    target_block = target_blocks[0]
    target_hash = (
        target_block.hash
        if hasattr(target_block, "hash")
        else str(target_block)
    )
    source_hash = (block.hash if hasattr(block, "hash") else str(block))

    if target_hash != source_hash:
        return SyncConflict(
            conflict_id=f"conflict-{int(time.time() * 1000)}",
            source_chain="mainchain",
            target_chain="subchain",
            block_index=block.index,
            source_hash=source_hash,
            target_hash=target_hash,
        )
    return None


class CrossLevelSyncManager:
    """
    Manages state synchronization across hierarchy levels.

    Handles bidirectional sync between MainChain and Sub-chains:
    - MainChain → Sub-chain: Push global state updates down
    - Sub-chain → MainChain: Submit proofs and anchors up

    The sync uses proof-based verification to ensure integrity
    across hierarchy levels.
    """

    def __init__(
        self,
        node_id: str,
        hierarchy_level: str = "subchain",
        batch_size: int = 100,
        sync_timeout: float = 30.0,
        conflict_strategy: ConflictResolutionStrategy = (
            ConflictResolutionStrategy.MAINCHAIN_WINS
        ),
        block_verifier: Any = None,
        proof_verifier: Any = None,
    ):
        """
        Initialize CrossLevelSyncManager.

        Args:
            node_id: ID of this node.
            hierarchy_level: "mainchain" or "subchain".
            batch_size: Max blocks per sync batch.
            sync_timeout: Timeout for sync operations.
            conflict_strategy: How to resolve conflicts.
            block_verifier: BlockVerifier for verification.
            proof_verifier: ZKVerifier for proof verification.
        """
        self.node_id = node_id
        self.hierarchy_level = hierarchy_level
        self.batch_size = batch_size
        self.sync_timeout = sync_timeout
        self.conflict_strategy = conflict_strategy
        self._block_verifier = block_verifier
        self._proof_verifier = proof_verifier

        # State
        self._status = CrossLevelSyncStatus.IDLE
        self._current_request: CrossLevelSyncRequest | None = None
        self._pending_blocks: list[Any] = []
        self._conflicts: list[SyncConflict] = []

        # Connected chains
        self._mainchain_ref: Any = None
        self._subchains: dict[str, Any] = {}

        # Callbacks
        self._on_sync_complete: Callable[
            [SyncResult], None
        ] | None = None
        self._on_conflict: Callable[
            [SyncConflict], ConflictResolutionStrategy
        ] | None = None

        # Stats
        self._stats = {
            "syncs_initiated": 0,
            "syncs_completed": 0,
            "syncs_failed": 0,
            "blocks_synced_down": 0,
            "blocks_synced_up": 0,
            "proofs_verified": 0,
            "conflicts_total": 0,
            "conflicts_resolved": 0,
        }

        logger.info(
            f"CrossLevelSyncManager initialized "
            f"(level={hierarchy_level}, batch_size={batch_size})"
        )

    def connect_mainchain(self, mainchain: Any) -> None:
        """Connect to the MainChain for sync operations."""
        self._mainchain_ref = mainchain
        logger.info("Connected to MainChain")

    def connect_subchain(self, subchain_id: str, subchain: Any) -> None:
        """Connect a Sub-chain for sync operations."""
        self._subchains[subchain_id] = subchain
        logger.info(f"Connected Sub-chain: {subchain_id}")

    def disconnect_subchain(self, subchain_id: str) -> None:
        """Disconnect a Sub-chain."""
        if subchain_id in self._subchains:
            del self._subchains[subchain_id]
            logger.info(f"Disconnected Sub-chain: {subchain_id}")

    def sync_from_mainchain(
        self,
        sub_chain_id: str,
        from_block: int = 0,
        to_block: int = -1,
    ) -> SyncResult:
        """
        Sync state from MainChain to a Sub-chain (gap-fill down).

        Args:
            sub_chain_id: Target sub-chain ID.
            from_block: Starting block index.
            to_block: Ending block index (-1 for latest).

        Returns:
            SyncResult with operation outcome.
        """
        start_time = time.time()
        self._stats["syncs_initiated"] += 1

        # Guard clauses for early exit
        validation_error = self._validate_connections(sub_chain_id)
        if validation_error:
            return validation_error

        self._status = CrossLevelSyncStatus.SYNCING_DOWN
        subchain = self._subchains[sub_chain_id]

        try:
            state_root_before = _get_state_root(subchain)
            
            if to_block == -1:
                to_block = _get_chain_height(self._mainchain_ref)

            # Core sync logic extracted to helper
            blocks_synced = self._sync_batches(subchain, from_block, to_block)

            # Update stats and status
            self._stats["blocks_synced_down"] += blocks_synced
            self._stats["syncs_completed"] += 1
            self._status = CrossLevelSyncStatus.COMPLETE

            result = SyncResult(
                success=True,
                blocks_synced=blocks_synced,
                conflicts_found=len(self._conflicts),
                conflicts_resolved=len([c for c in self._conflicts if c.resolved]),
                duration_seconds=time.time() - start_time,
                state_root_before=state_root_before,
                state_root_after=_get_state_root(subchain),
            )

            if self._on_sync_complete:
                self._on_sync_complete(result)

            logger.info(f"Sync from MainChain complete: {blocks_synced} blocks to {sub_chain_id}")
            return result

        except Exception as e:
            logger.error(f"Sync from MainChain failed: {e}")
            self._stats["syncs_failed"] += 1
            self._status = CrossLevelSyncStatus.FAILED
            return SyncResult(success=False, error_message=str(e), duration_seconds=time.time() - start_time)

    def sync_to_mainchain(self, sub_chain_id: str, proof: bytes | None = None) -> SyncResult:
        """
        Sync state from Sub-chain to MainChain (proof submission up).

        Args:
            sub_chain_id: Source sub-chain ID.
            proof: Optional pre-computed proof.

        Returns:
            SyncResult with operation outcome.
        """
        start_time = time.time()
        self._stats["syncs_initiated"] += 1

        # Guard clauses
        validation_error = self._validate_connections(sub_chain_id)
        if validation_error:
            return validation_error

        self._status = CrossLevelSyncStatus.SYNCING_UP
        subchain = self._subchains[sub_chain_id]

        try:
            state_root = _get_state_root(subchain)
            block_height = _get_chain_height(subchain)

            # 1. Prepare and verify proof
            if proof is None:
                proof = _generate_proof(subchain, block_height)

            self._status = CrossLevelSyncStatus.VERIFYING
            if not self._verify_proof(proof, state_root):
                return self._handle_sync_failure("Proof verification failed", start_time)

            self._stats["proofs_verified"] += 1

            # 2. Submit anchor
            anchor_data = {
                "sub_chain_id": sub_chain_id,
                "block_height": block_height,
                "state_root": state_root,
                "proof_hash": hashlib.sha256(proof).hexdigest(),
                "timestamp": time.time(),
            }

            if not self._submit_anchor_to_mainchain(anchor_data):
                return self._handle_sync_failure("Failed to submit anchor to MainChain", start_time)

            # 3. Handle success
            return self._handle_sync_success(sub_chain_id, state_root, start_time)

        except Exception as e:
            logger.error(f"Sync to MainChain failed: {e}")
            return self._handle_sync_failure(str(e), start_time)

    def _handle_sync_failure(self, error_message: str, start_time: float) -> SyncResult:
        """Helper to handle sync failure and return result."""
        self._stats["syncs_failed"] += 1
        self._status = CrossLevelSyncStatus.FAILED
        return SyncResult(
            success=False,
            error_message=error_message,
            duration_seconds=time.time() - start_time,
        )

    def _handle_sync_success(self, sub_chain_id: str, state_root: str, start_time: float) -> SyncResult:
        """Helper to handle sync success and return result."""
        self._stats["blocks_synced_up"] += 1
        self._stats["syncs_completed"] += 1
        self._status = CrossLevelSyncStatus.COMPLETE

        result = SyncResult(
            success=True,
            blocks_synced=1,
            duration_seconds=time.time() - start_time,
            state_root_after=state_root,
        )

        if self._on_sync_complete:
            self._on_sync_complete(result)

        logger.info(f"Sync to MainChain complete: anchor from {sub_chain_id}")
        return result

    def verify_cross_level_state(self, source_chain_id: str, target_chain_id: str) -> bool:
        """
        Verify state consistency between two hierarchy levels.

        Args:
            source_chain_id: Source chain identifier.
            target_chain_id: Target chain identifier.

        Returns:
            True if states are consistent.
        """
        source = self._get_chain_by_id(source_chain_id)
        target = self._get_chain_by_id(target_chain_id)

        if not source or not target:
            logger.warning("Cannot verify: chain not found")
            return False

        source_root = _get_state_root(source)
        target_root = _get_state_root(target)

        # For sub-chain to main-chain, verify anchor exists
        if source_chain_id != "mainchain" and target_chain_id == "mainchain":
            return _verify_anchor_exists(target, source_chain_id, source_root)

        # For same-level comparison, roots should match
        return source_root == target_root

    def resolve_sync_conflict(self,conflict: SyncConflict) -> bool:
        """
        Resolve a sync conflict.

        Args:
            conflict: The conflict to resolve.

        Returns:
            True if conflict was resolved.
        """
        self._status = CrossLevelSyncStatus.RESOLVING_CONFLICT
        self._stats["conflicts_total"] += 1

        # Use callback if available
        strategy = self.conflict_strategy
        if self._on_conflict:
            strategy = self._on_conflict(conflict)

        # Apply resolution strategy
        if strategy == ConflictResolutionStrategy.MAINCHAIN_WINS:
            conflict.resolution = "Used MainChain state"
            conflict.resolved = True
        elif strategy == ConflictResolutionStrategy.SUBCHAIN_WINS:
            conflict.resolution = "Used SubChain state"
            conflict.resolved = True
        elif strategy == ConflictResolutionStrategy.LATEST_TIMESTAMP:
            conflict.resolution = "Used latest timestamp"
            conflict.resolved = True
        elif strategy == ConflictResolutionStrategy.MANUAL:
            logger.warning("Manual conflict resolution required")
            return False

        if conflict.resolved:
            self._stats["conflicts_resolved"] += 1
            logger.info(
                f"Resolved conflict {conflict.conflict_id}: "
                f"{conflict.resolution}"
            )

        return conflict.resolved

    def get_pending_conflicts(self) -> list[SyncConflict]:
        """Get list of unresolved conflicts."""
        return [c for c in self._conflicts if not c.resolved]

    def get_status(self) -> CrossLevelSyncStatus:
        """Get current sync status."""
        return self._status

    def get_stats(self) -> dict[str, Any]:
        """Get sync statistics."""
        return {
            **self._stats,
            "status": self._status.value,
            "pending_conflicts": len(self.get_pending_conflicts()),
            "connected_subchains": len(self._subchains),
            "mainchain_connected": self._mainchain_ref is not None,
        }

    def set_callbacks(
        self,
        on_complete: Callable[[SyncResult], None] | None = None,
        on_conflict: Callable[[SyncConflict], ConflictResolutionStrategy] | None = None,
    ) -> None:
        """Set callback functions."""
        self._on_sync_complete = on_complete
        self._on_conflict = on_conflict

    def reset(self) -> None:
        """Reset sync state."""
        self._status = CrossLevelSyncStatus.IDLE
        self._current_request = None
        self._pending_blocks.clear()
        self._conflicts.clear()

    def _validate_connections(self, sub_chain_id: str) -> SyncResult | None:
        """Validate that MainChain and the specified Sub-chain are connected."""
        if not self._mainchain_ref:
            return SyncResult(success=False, error_message="MainChain not connected")

        if sub_chain_id not in self._subchains:
            return SyncResult(success=False, error_message=f"Sub-chain {sub_chain_id} not connected")
        
        return None

    # Helper methods

    def _get_chain_by_id(self, chain_id: str) -> Any:
        """Get chain reference by ID."""
        if chain_id == "mainchain":
            return self._mainchain_ref
        return self._subchains.get(chain_id)

    def _verify_block(self, block: Any) -> bool:
        """Verify a block."""
        if self._block_verifier:
            result = self._block_verifier.verify_block(block)
            return result.is_valid() if hasattr(result, "is_valid") else result
        return True

    def _verify_proof(self, proof: bytes, state_root: str) -> bool:
        """Verify a proof."""
        if self._proof_verifier:
            return self._proof_verifier.verify(proof, state_root)
        # Mock verification
        return len(proof) > 0

    def _sync_batches(self, subchain: Any, from_block: int, to_block: int) -> int:
        """Process sync in batches and return total blocks synced."""
        total_synced = 0
        for batch_start in range(from_block, to_block, self.batch_size):
            batch_end = min(batch_start + self.batch_size, to_block)
            blocks = _get_blocks(self._mainchain_ref, batch_start, batch_end)
            
            for block in blocks:
                if self._process_block_sync(subchain, block):
                    total_synced += 1
        return total_synced

    def _process_block_sync(self, subchain: Any, block: Any) -> bool:
        """Process a single block during sync. Returns True if block was applied."""
        if not self._verify_block(block):
            logger.warning(f"Block failed verification during sync")
            return False

        conflict = _check_conflict(subchain, block)
        if conflict:
            self._conflicts.append(conflict)
            if not self._resolve_conflict(conflict):
                return False

        return _apply_block_to_chain(subchain, block)

    def _resolve_conflict(self, conflict: SyncConflict) -> bool:
        """Resolve a conflict."""
        return self.resolve_sync_conflict(conflict)

    def _submit_anchor_to_mainchain(self, anchor_data: dict) -> bool:
        """Submit anchor event to MainChain."""
        if not self._mainchain_ref:
            return False

        try:
            if hasattr(self._mainchain_ref, "receive_proof"):
                return self._mainchain_ref.receive_proof(anchor_data)
            if hasattr(self._mainchain_ref, "add_event"):
                return self._mainchain_ref.add_event({
                    "event_type": "subchain_anchor",
                    **anchor_data,
                })
            return True
        except Exception as e:
            logger.error(f"Failed to submit anchor: {e}")
            return False
