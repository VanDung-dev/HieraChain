from __future__ import annotations

import os
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any

from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
from hierachain.cluster.cross_level_sync_types import ConflictResolutionStrategy
from hierachain.config.settings import settings

if TYPE_CHECKING:
    from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager


def _build_cross_level_sync(
    main_chain: Any, node_identity: Any | None
) -> CrossLevelSyncManager | None:
    if not settings.CROSS_LEVEL_SYNC_ENABLED:
        return None
    sync = CrossLevelSyncManager(
        node_id=getattr(node_identity, "node_id", "main-node"),
        hierarchy_level="mainchain",
        batch_size=settings.CROSS_LEVEL_SYNC_BATCH_SIZE,
        sync_timeout=settings.CROSS_LEVEL_SYNC_TIMEOUT,
        conflict_strategy=ConflictResolutionStrategy.MAINCHAIN_WINS,
        block_verifier=None,
        proof_verifier=None,
    )
    sync.connect_mainchain(main_chain)
    return sync


def initialize(manager: HierarchyManager, node_identity: Any | None) -> None:
    with ExitStack() as cleanup:
        cleanup.callback(manager._close_transaction_manager)
        if os.path.lexists(os.path.join("data", "transactions")):
            _ = manager.transaction_manager

        manager.cross_level_sync = _build_cross_level_sync(
            manager.main_chain, node_identity
        )

        manager.storage = manager._create_storage()
        if manager.storage is not None:
            cleanup.callback(manager.storage.close)
            if not manager.storage.store_chain(manager.main_chain):
                raise RuntimeError("Failed to persist main chain metadata")
            manager.main_chain.proof_storage = manager.storage
            manager._restore_main_chain()
            if manager.cross_level_sync is not None:
                manager.cross_level_sync.storage = manager.storage
            manager._restore_sub_chains()
            for chain in manager.sub_chains.values():
                cleanup.callback(chain.shutdown)
            manager._restore_hierarchy_registry()
        cleanup.pop_all()
