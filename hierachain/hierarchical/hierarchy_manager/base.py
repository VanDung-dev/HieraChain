"""
HierarchyManager class — coordinates Main Chain and Sub-Chains.

Behavior is composed from responsibility-specific mixins:
    - ``ChainOperationsMixin``        - sub-chain creation and registration
    - ``OrganizationOperationsMixin`` - organizations, channels, access control
    - ``SystemOperationsMixin``       - system reports and maintenance
    - ``TransactionCoordinationMixin`` - cross-chain coordinator plumbing
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any

from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
from hierachain.cluster.cross_level_sync_types import (
    ConflictResolutionStrategy,
)
from hierachain.config.settings import settings
from hierachain.hierarchical.channel import Channel
from hierachain.hierarchical.hierarchy_manager import recovery, registry, storage_factory
from hierachain.hierarchical.hierarchy_manager.chain_ops import ChainOperationsMixin
from hierachain.hierarchical.hierarchy_manager.org_ops import (
    OrganizationOperationsMixin,
)
from hierachain.hierarchical.hierarchy_manager.system_ops import SystemOperationsMixin
from hierachain.hierarchical.hierarchy_manager.transaction_ops import (
    TransactionCoordinationMixin,
)
from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.multi_org import MultiOrgNetwork
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager

if TYPE_CHECKING:
    from hierachain.domains.chains.domain_chain import DomainChain


class HierarchyManager(
    ChainOperationsMixin,
    OrganizationOperationsMixin,
    SystemOperationsMixin,
    TransactionCoordinationMixin,
):
    """
    Manages the hierarchy of chains (Main Chain and Sub-Chains).

    This class handles:
    - Creation and registration of sub-chains
    - Routing of inter-chain communication
    - Aggregation of system-wide statistics
    - Coordination of cross-chain transactions (via TransactionManager)
    """

    def __init__(self, name: str = "MainChain", node_identity: Any | None = None):
        """Initialize main chain."""
        self.main_chain: MainChain = MainChain(name, node_identity=node_identity)
        self.sub_chains: dict[str, DomainChain] = {}
        self.system_started_at: float = time.time()
        self.node_identity = self.main_chain.node_identity

        self.auto_proof_submission: bool = False
        self.proof_submission_interval: int = 60

        self.system_stats: dict[str, Any] = {
            "total_transactions": 0,
            "total_blocks": 0,
            "active_chains": 0,
        }

        self.organizations: dict[str, Any] = {}
        self.chain_access: dict[str, dict[str, list[str]]] = {}
        self.network: MultiOrgNetwork | None = None
        self.channels: dict[str, Channel] = {}
        self.private_collections: dict[str, Any] = {}
        self._registry_lock = threading.RLock()
        self._registry_state: dict[str, Any] | None = None
        self._registry_mutating = False

        self._transaction_manager: Any | None = None
        self._closed = False

        # Bootstrap owns these resources until all recovery steps succeed.
        with ExitStack() as cleanup:
            cleanup.callback(self._close_transaction_manager)
            # Registry/channel workers need no 2PC writer. Existing decisions
            # must still be recovered, with the journal's exclusive lease.
            if os.path.lexists(os.path.join("data", "transactions")):
                _ = self.transaction_manager
            self.cross_level_sync: CrossLevelSyncManager | None = None
            if settings.CROSS_LEVEL_SYNC_ENABLED:
                sync = CrossLevelSyncManager(
                    node_id=getattr(node_identity, "node_id", "main-node"),
                    hierarchy_level="mainchain",
                    batch_size=settings.CROSS_LEVEL_SYNC_BATCH_SIZE,
                    sync_timeout=settings.CROSS_LEVEL_SYNC_TIMEOUT,
                    conflict_strategy=ConflictResolutionStrategy.MAINCHAIN_WINS,
                    block_verifier=None,
                    proof_verifier=None,
                )
                sync.connect_mainchain(self.main_chain)
                self.cross_level_sync = sync

            self.storage = self._create_storage()
            if self.storage is not None:
                cleanup.callback(self.storage.close)
                if not self.storage.store_chain(self.main_chain):
                    raise RuntimeError("Failed to persist main chain metadata")
                self.main_chain.proof_storage = self.storage
                self._restore_main_chain()
                if self.cross_level_sync is not None:
                    self.cross_level_sync.storage = self.storage
                self._restore_sub_chains()
                for chain in self.sub_chains.values():
                    cleanup.callback(chain.shutdown)
                self._restore_hierarchy_registry()
            cleanup.pop_all()

    @property
    def transaction_manager(self) -> CrossChainTransactionManager:
        """Acquire the single coordinator writer only when needed."""
        if getattr(self, "_closed", False):
            raise RuntimeError("Hierarchy manager is closed")
        if self._transaction_manager is not None:
            return self._transaction_manager
        with self._registry_lock:
            if self._closed:
                raise RuntimeError("Hierarchy manager is closed")
            if self._transaction_manager is None:
                self._transaction_manager = CrossChainTransactionManager(self)
            return self._transaction_manager

    @transaction_manager.setter
    def transaction_manager(self, manager: CrossChainTransactionManager) -> None:
        self._transaction_manager = manager

    def _close_transaction_manager(self) -> None:
        if self._transaction_manager is not None:
            self._transaction_manager.journal.close()

    def close(self) -> None:
        """Release owned orderers, coordinator and storage without opening new resources."""
        with self._registry_lock:
            if self._closed:
                return
            self._closed = True
            with ExitStack() as cleanup:
                if self.storage is not None:
                    cleanup.callback(self.storage.close)
                cleanup.callback(self._close_transaction_manager)
                for chain in self.sub_chains.values():
                    cleanup.callback(chain.shutdown)

    def _restore_main_chain(self) -> None:
        """Restore and verify the signed MainChain history before accepting proofs."""
        return recovery._restore_main_chain(self)

    def _hierarchy_registry_snapshot(self) -> dict[str, Any]:
        return registry._hierarchy_registry_snapshot(self)

    def _persist_hierarchy_registry(self) -> bool:
        return registry._persist_hierarchy_registry(self)

    def _restore_hierarchy_registry(self) -> None:
        return registry._restore_hierarchy_registry(self)

    def _channel_registry_revision(self) -> str | None:
        return (self._registry_state or {}).get("_revision")

    def _bind_channel_ledger(self, channel: Channel) -> None:
        channel.ledger._lock = self._registry_lock
        if self.storage is not None:
            channel.ledger.bind_storage(self.storage, self._channel_registry_revision)

    def _apply_hierarchy_registry(self, state: dict[str, Any]) -> None:
        """Refresh access metadata; existing ledgers consume their own durable suffix."""
        return registry._apply_hierarchy_registry(self, state)

    def _mutate_registry(self, change: Callable[[], Any], failure_message: str) -> Any:
        return registry._mutate_registry(self, change, failure_message)

    def _restore_sub_chains(self) -> None:
        """Recreate every persisted sub-chain before serving API requests."""
        return recovery._restore_sub_chains(self)

    def get_sub_chain(self, name: str) -> DomainChain | None:
        return self.sub_chains.get(name)

    def get_all_sub_chains(self) -> dict[str, DomainChain]:
        return dict(self.sub_chains)

    def get_main_chain(self) -> MainChain:
        return self.main_chain

    @staticmethod
    def _create_storage() -> Any | None:
        return storage_factory.create_storage_backend()

    def set_main_chain(self, main_chain):
        self.main_chain = main_chain

    def __str__(self) -> str:
        return (
            f"HierarchyManager(main_chain={self.main_chain.name}, "
            f"sub_chains={len(self.sub_chains)})"
        )

    def __repr__(self) -> str:
        return (f"HierarchyManager(main_chain={self.main_chain.name}, "
                f"sub_chains={list(self.sub_chains.keys())}, "
                f"auto_proof={self.auto_proof_submission}, "
                f"uptime={time.time() - self.system_started_at:.2f}s)")
