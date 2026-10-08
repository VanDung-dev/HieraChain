"""Submit Sub-chain proofs to MainChain without merging chain histories."""

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from hierachain.cluster.cross_level_sync_types import (
    ConflictResolutionStrategy,
    CrossLevelSyncRequest,
    CrossLevelSyncStatus,
    SyncConflict,
    SyncResult,
)
from hierachain.consensus.ordering.storage import _block_from_dict

logger = logging.getLogger(__name__)


def _get_state_root(chain: Any) -> str:
    """Get state root from chain."""
    if hasattr(chain, "get_state_root"):
        return chain.get_state_root()
    height = _get_chain_height(chain)
    blocks = _get_blocks(chain, height - 1, height) if height else []
    if blocks:
        root = getattr(blocks[-1], "merkle_root", None)
        if root:
            return root
        if hasattr(blocks[-1], "hash"):
            return blocks[-1].hash
    raise RuntimeError("Chain does not expose a verifiable state root")


def _get_chain_height(chain: Any) -> int:
    """Get current chain height."""
    if hasattr(chain, "get_block_count"):
        return chain.get_block_count()
    if hasattr(chain, "blockchain"):
        return len(chain.blockchain.get_chain())
    if hasattr(chain, "chain"):
        return len(chain.chain)
    raise RuntimeError("Chain does not expose its block height")


def _get_blocks(chain: Any, from_idx: int, to_idx: int) -> list[Any]:
    """Get blocks from chain."""
    if hasattr(chain, "get_blocks"):
        return chain.get_blocks(from_idx, to_idx)
    if hasattr(chain, "blockchain"):
        all_blocks = chain.blockchain.get_chain()
        return all_blocks[from_idx:to_idx]
    if hasattr(chain, "chain"):
        return chain.chain[from_idx:to_idx]
    raise RuntimeError("Chain does not expose blocks for synchronization")


def _find_anchor_block(
    mainchain: Any, subchain_id: str, state_root: str, proof_hash: str | None = None
) -> Any | None:
    """Find a finalized in-memory block containing the requested proof."""
    chain = getattr(mainchain, "chain", None)
    if not isinstance(chain, list):
        return None

    # ponytail: O(chain length) proof scan; add a finalized index if this path is hot.
    for block in chain:
        events = (
            block.to_event_list()
            if hasattr(block, "to_event_list")
            else getattr(block, "events", [])
        )
        for event in events:
            details = event.get("details", {})
            metadata = event.get("metadata", {})
            if (
                event.get("event") == "proof_submission"
                and isinstance(details, dict)
                and details.get("sub_chain_name") == subchain_id
                and (proof_hash is None or details.get("proof_hash") == proof_hash)
                and isinstance(metadata, dict)
                and metadata.get("latest_merkle_root") == state_root
            ):
                return block
    return None


def _verify_anchor_exists(
    mainchain: Any, subchain_id: str, state_root: str, proof_hash: str | None = None
) -> bool:
    """Verify that the anchor survives a signed durable-storage readback."""
    block = _find_anchor_block(mainchain, subchain_id, state_root, proof_hash)
    storage = getattr(mainchain, "proof_storage", None)
    if block is None or not callable(getattr(storage, "get_block_by_index", None)):
        return False
    try:
        stored = storage.get_block_by_index(block.index, mainchain.name)
        if not isinstance(stored, dict) or stored.get("hash") != block.hash:
            return False
        _block_from_dict(stored, mainchain.trusted_public_keys)
        return True
    except Exception:
        logger.exception("Could not verify durable proof anchor for %s", subchain_id)
        return False


def _persist_proof_anchor(
    mainchain: Any, storage: Any, subchain_id: str, state_root: str, proof_hash: str
) -> bool:
    """Finalize the proof and read back every signed block from durable storage."""
    from hierachain.hierarchical.main_chain.proofs import _refresh_durable_proofs

    if storage is None or not all(
        callable(getattr(storage, name, None))
        for name in ("save_block", "get_block_by_index")
    ):
        return False

    with mainchain.lock:
        if _find_anchor_block(mainchain, subchain_id, state_root, proof_hash) is None:
            if mainchain.finalize_block() is None:
                return False
        if _find_anchor_block(mainchain, subchain_id, state_root, proof_hash) is None:
            return False

        # ponytail: Recheck the full signed history; use a verified persisted tip if proof volume grows.
        for block in mainchain.chain:
            stored = storage.get_block_by_index(block.index, mainchain.name)
            if stored is None:
                data = block.to_dict()
                data["chain_name"] = mainchain.name
                data["metadata"] = {
                    "merkle_root": block.merkle_root,
                    "creator_id": block.creator_id,
                    "signature": block.signature,
                }
                if storage.save_block(data) is not True:
                    return False
                stored = storage.get_block_by_index(block.index, mainchain.name)
            if not isinstance(stored, dict) or stored.get("hash") != block.hash:
                return False
            _block_from_dict(stored, mainchain.trusted_public_keys)

        _refresh_durable_proofs(mainchain)
        return _verify_anchor_exists(mainchain, subchain_id, state_root, proof_hash)


# --- Resolution strategy lookup ---
_RESOLUTION_MAP: dict[ConflictResolutionStrategy, str] = {
    ConflictResolutionStrategy.MAINCHAIN_WINS: "Used MainChain state",
    ConflictResolutionStrategy.SUBCHAIN_WINS: "Used SubChain state",
    ConflictResolutionStrategy.LATEST_TIMESTAMP: "Used latest timestamp",
}


def _apply_resolution_strategy(
    conflict: SyncConflict,
    strategy: ConflictResolutionStrategy,
) -> bool:
    """Apply a conflict resolution strategy to a SyncConflict."""
    if strategy == ConflictResolutionStrategy.MANUAL:
        logger.warning("Manual conflict resolution required")
        return False

    resolution_msg = _RESOLUTION_MAP.get(strategy)
    if resolution_msg:
        conflict.resolution = resolution_msg
        conflict.resolved = True
        return True

    return False


def _verify_proof_with(
    verifier: Any, proof: bytes, public_inputs: dict[str, Any]
) -> bool:
    """Verify a proof using a verifier instance."""
    if not verifier:
        return False
    result = verifier.verify(proof, public_inputs)
    return result.is_valid() if hasattr(result, "is_valid") else bool(result)


def _get_chain_ref(
    chain_id: str,
    mainchain_ref: Any,
    subchains: dict[str, Any],
) -> Any:
    """Get chain reference by ID."""
    if chain_id == "mainchain":
        return mainchain_ref
    return subchains.get(chain_id)


class CrossLevelSyncManager:
    """
    Records Sub-chain proofs in MainChain. MainChain and Sub-chain blocks have
    separate histories, so raw MainChain blocks are not copied into Sub-chains.
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
        storage: Any = None,
    ):
        """
        Initialize CrossLevelSyncManager.

        Args:
            node_id: ID of this node.
            hierarchy_level: "mainchain" or "subchain".
            batch_size: Legacy option retained for caller compatibility.
            sync_timeout: Timeout for sync operations.
            conflict_strategy: How to resolve conflicts.
            block_verifier: Legacy option; parent blocks are not copied down.
            proof_verifier: Optional verifier for a supplied proof.
        """
        self.node_id = node_id
        self.hierarchy_level = hierarchy_level
        self.sync_timeout = sync_timeout
        self.conflict_strategy = conflict_strategy
        self._proof_verifier = proof_verifier
        self.storage = storage

        # State
        self._status = CrossLevelSyncStatus.IDLE
        self._state_lock = threading.RLock()
        self._active_operations: dict[CrossLevelSyncStatus, int] = {}
        self._batch_failed = False
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
        if self.storage is not None and hasattr(mainchain, "proof_storage"):
            mainchain.proof_storage = self.storage
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
        """Reject raw parent block copying while tracking aggregate activity."""
        with self._operation(CrossLevelSyncStatus.SYNCING_DOWN):
            return self._sync_from_mainchain(sub_chain_id, from_block, to_block)

    def _sync_from_mainchain(
        self, sub_chain_id: str, from_block: int, to_block: int,
    ) -> SyncResult:
        """Reject copying MainChain blocks into a Sub-chain's history."""
        start_time = time.time()
        self._increment_stat("syncs_initiated")

        validation_error = self._validate_connections(sub_chain_id)
        if validation_error:
            return self._handle_sync_failure(
                validation_error.error_message, start_time
            )

        return self._handle_sync_failure(
            "Raw MainChain block sync into a Sub-chain is unsupported; "
            "each chain has its own history and genesis.",
            start_time,
        )

    def sync_to_mainchain(
        self, sub_chain_id: str, proof: bytes | None = None
    ) -> SyncResult:
        """Submit a Sub-chain proof and track all overlapping operations."""
        with self._operation(CrossLevelSyncStatus.SYNCING_UP):
            return self._sync_to_mainchain(sub_chain_id, proof)

    def _sync_to_mainchain(
        self, sub_chain_id: str, proof: bytes | None = None,
    ) -> SyncResult:
        """
        Sync state from Sub-chain to MainChain (proof submission up).

        Args:
            sub_chain_id: Source sub-chain ID.
            proof: Optional pre-computed proof.

        Returns:
            SyncResult with operation outcome.
        """
        start_time = time.time()
        self._increment_stat("syncs_initiated")

        validation_error = self._validate_connections(sub_chain_id)
        if validation_error:
            return self._handle_sync_failure(
                validation_error.error_message, start_time
            )

        try:
            subchain = self._subchains[sub_chain_id]
            state_root = _get_state_root(subchain)
            latest_block = subchain.get_latest_block()
            previous_block = (
                subchain.chain[-2] if len(subchain.chain) > 1 else None
            )
            public_inputs = {
                "old_state_root": (
                    previous_block.merkle_root if previous_block is not None else "genesis"
                ),
                "new_state_root": latest_block.merkle_root or latest_block.hash,
                "block_index": latest_block.index,
                "sub_chain_name": sub_chain_id,
            }

            if proof is not None:
                verifier = self._proof_verifier or getattr(
                    self._mainchain_ref, "zk_verifier", None
                )
                if verifier is None:
                    return self._handle_sync_failure(
                        "No proof verifier configured", start_time
                    )
                if not _verify_proof_with(verifier, proof, public_inputs):
                    return self._handle_sync_failure(
                        "Proof verification failed", start_time
                    )
                self._increment_stat("proofs_verified")

            if not callable(getattr(subchain, "submit_proof_to_main", None)):
                return self._handle_sync_failure(
                    "Sub-chain does not support proof submission", start_time
                )
            if not callable(getattr(self._mainchain_ref, "add_proof", None)):
                return self._handle_sync_failure(
                    "MainChain does not support proof records", start_time
                )

            if not subchain.submit_proof_to_main(
                self._mainchain_ref, zk_proof=proof
            ):
                return self._handle_sync_failure(
                    "MainChain rejected or could not persist the Sub-chain proof", start_time
                )

            if not _verify_anchor_exists(
                self._mainchain_ref,
                sub_chain_id,
                state_root,
                latest_block.hash,
            ):
                return self._handle_sync_failure(
                    "MainChain proof could not be verified in durable storage", start_time
                )

            return self._handle_sync_success(sub_chain_id, state_root, start_time)

        except Exception as e:
            logger.error("Sync to MainChain failed: %s", e)
            return self._handle_sync_failure(str(e), start_time)

    def _handle_sync_failure(self, error_message: str, start_time: float) -> SyncResult:
        """Helper to handle sync failure and return result."""
        with self._state_lock:
            self._stats["syncs_failed"] += 1
            self._batch_failed = True
        return SyncResult(
            success=False,
            error_message=error_message,
            duration_seconds=time.time() - start_time,
        )

    def _handle_sync_success(
        self,
        sub_chain_id: str,
        state_root: str,
        start_time: float,
    ) -> SyncResult:
        """Helper to handle sync success and return result."""
        with self._state_lock:
            self._stats["blocks_synced_up"] += 1
            self._stats["syncs_completed"] += 1

        result = SyncResult(
            success=True,
            blocks_synced=1,
            duration_seconds=time.time() - start_time,
            state_root_after=state_root,
        )

        if self._on_sync_complete:
            try:
                self._on_sync_complete(result)
            except Exception:
                logger.exception("Sync completion callback failed after the anchor was committed")

        logger.info("Sync to MainChain complete: anchor from %s", sub_chain_id)
        return result

    def verify_cross_level_state(
        self, source_chain_id: str, target_chain_id: str
    ) -> bool:
        """
        Verify state consistency between two hierarchy levels.

        Args:
            source_chain_id: Source chain identifier.
            target_chain_id: Target chain identifier.

        Returns:
            True if states are consistent.
        """
        source = _get_chain_ref(
            source_chain_id,
            self._mainchain_ref,
            self._subchains,
        )
        target = _get_chain_ref(
            target_chain_id,
            self._mainchain_ref,
            self._subchains,
        )

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

    def resolve_sync_conflict(self, conflict: SyncConflict) -> bool:
        """Resolve a conflict while preserving active sync status."""
        with self._operation(CrossLevelSyncStatus.RESOLVING_CONFLICT):
            resolved = self._resolve_sync_conflict(conflict)
            if not resolved:
                with self._state_lock:
                    self._batch_failed = True
            return resolved

    def _resolve_sync_conflict(self, conflict: SyncConflict) -> bool:
        """
        Resolve a sync conflict.

        Args:
            conflict: The conflict to resolve.

        Returns:
            True if conflict was resolved.
        """
        self._increment_stat("conflicts_total")

        # Use callback if available
        strategy = self.conflict_strategy
        if self._on_conflict:
            strategy = self._on_conflict(conflict)

        resolved = _apply_resolution_strategy(conflict, strategy)

        if resolved:
            self._increment_stat("conflicts_resolved")
            logger.info(
                "Resolved conflict %s: %s",
                conflict.conflict_id,
                conflict.resolution,
            )

        return resolved

    def get_pending_conflicts(self) -> list[SyncConflict]:
        """Get list of unresolved conflicts."""
        return [c for c in self._conflicts if not c.resolved]

    def get_status(self) -> CrossLevelSyncStatus:
        """Get current sync status."""
        with self._state_lock:
            return self._status

    def get_stats(self) -> dict[str, Any]:
        """Get sync statistics."""
        with self._state_lock:
            return {
                **self._stats,
                "status": self._status.value,
                "active_operations": sum(self._active_operations.values()),
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
        with self._state_lock:
            if self._active_operations:
                raise RuntimeError("Cannot reset while sync operations are active")
            self._status = CrossLevelSyncStatus.IDLE
            self._batch_failed = False
            self._current_request = None
            self._pending_blocks.clear()
            self._conflicts.clear()

    def _increment_stat(self, name: str) -> None:
        with self._state_lock:
            self._stats[name] += 1

    @contextmanager
    def _operation(self, status: CrossLevelSyncStatus) -> Iterator[None]:
        """Keep a terminal status hidden until every overlapping operation finishes."""
        with self._state_lock:
            if not self._active_operations:
                self._batch_failed = False
            self._active_operations[status] = self._active_operations.get(status, 0) + 1
            self._status = next(iter(self._active_operations))
        try:
            yield
        except Exception:
            with self._state_lock:
                self._batch_failed = True
            raise
        finally:
            with self._state_lock:
                self._active_operations[status] -= 1
                if not self._active_operations[status]:
                    del self._active_operations[status]
                self._status = (
                    next(iter(self._active_operations)) if self._active_operations
                    else CrossLevelSyncStatus.FAILED if self._batch_failed
                    else CrossLevelSyncStatus.COMPLETE
                )

    def _validate_connections(self, sub_chain_id: str) -> SyncResult | None:
        """Validate MainChain and Sub-chain are connected."""
        if not self._mainchain_ref:
            return SyncResult(
                success=False,
                error_message="MainChain not connected",
            )

        if sub_chain_id not in self._subchains:
            return SyncResult(
                success=False,
                error_message=(
                    f"Sub-chain {sub_chain_id} not connected"
                ),
            )

        return None
