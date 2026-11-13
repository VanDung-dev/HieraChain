"""
HierarchyManager class — coordinates Main Chain and Sub-Chains.

Behavior is composed from responsibility-specific mixins:
    - ``OrganizationOperationsMixin`` - organizations, channels, access control
    - ``SystemOperationsMixin``       - system reports and maintenance
    - ``TransactionCoordinationMixin`` - cross-chain coordinator plumbing
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
from hierachain.cluster.cross_level_sync_types import (
    ConflictResolutionStrategy,
)
from hierachain.config.settings import settings
from hierachain.hierarchical.channel import Channel
from hierachain.hierarchical.hierarchy_manager import recovery, registry
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

logger = logging.getLogger(__name__)


class HierarchyManager(
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

    def create_sub_chain(
        self, name: str, domain_type: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        existing = self.sub_chains.get(name)
        if existing is not None and (
            callable(getattr(existing, "prepare_transaction", None))
            or getattr(existing, "domain_type", None) != domain_type
        ):
            return False

        from hierachain.domains.chains.domain_chain import DomainChain

        sub_chain = DomainChain(name, domain_type, metadata=metadata)

        try:
            if existing is None:
                self.add_sub_chain(name, sub_chain)
            else:
                self._replace_sub_chain_placeholder(name, existing, sub_chain)
        except Exception:
            sub_chain.shutdown()
            raise

        return True

    def _replace_sub_chain_placeholder(self, name: str, placeholder: Any, chain: DomainChain) -> None:
        """Replace a restored generic chain with its concrete DomainChain participant."""
        # Keep the placeholder running until its replacement is connected. Rewriting
        # existing chain metadata here could delete SQLite block rows via REPLACE.
        if not chain.connect_to_main_chain(self.main_chain):
            raise RuntimeError(f"Failed to connect sub-chain to main chain: {name}")

        self.sub_chains[name] = chain
        if self.cross_level_sync:
            self.cross_level_sync.connect_subchain(name, chain)

        try:
            placeholder.shutdown()
        except Exception:
            logger.exception("Could not shut down replaced sub-chain placeholder %s", name)

        self.transaction_manager.retry_pending()

    def get_sub_chain(self, name: str) -> DomainChain | None:
        return self.sub_chains.get(name)

    def get_all_sub_chains(self) -> dict[str, DomainChain]:
        return dict(self.sub_chains)

    def get_main_chain(self) -> MainChain:
        return self.main_chain

    @staticmethod
    def _create_storage() -> Any | None:
        backend = getattr(settings, "STORAGE_BACKEND", settings.DEFAULT_STORAGE_BACKEND)

        def create_sqlite_storage() -> SQLiteAdapter:
            db_path = "hierachain.db"
            if settings.DATABASE_URL.startswith("sqlite:///"):
                db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            return SQLiteAdapter(database_path=db_path)

        if backend == "sqlite":
            return create_sqlite_storage()

        if backend in ("postgres", "postgresql"):
            postgres = None
            try:
                from hierachain.adapters.database.postgres_adapter import (
                    PostgresAdapter,
                )

                postgres = PostgresAdapter(database_url=settings.DATABASE_URL)
                with postgres._get_connection() as connection:
                    connection.cursor().execute("SELECT 1 FROM chains LIMIT 0")
                return postgres
            except Exception as exc:
                if postgres is not None:
                    postgres.close()
                raise RuntimeError("Configured PostgreSQL storage is unavailable") from exc

        if backend == "redis":
            from hierachain.adapters.database.redis_ledger import RedisLedgerAdapter

            return RedisLedgerAdapter()

        if backend == "memory":
            return None
        raise ValueError(f"Unsupported HRC_STORAGE_BACKEND value: {backend!r}")

    def set_main_chain(self, main_chain):
        self.main_chain = main_chain

    def add_sub_chain(self, chain_name, sub_chain, *, persist: bool = True):
        with self._registry_lock:
            if chain_name in self.sub_chains:
                raise ValueError(f"Sub-chain {chain_name} already exists")

            if hasattr(sub_chain, "auto_proof_submission"):
                sub_chain.auto_proof_submission = self.auto_proof_submission
                sub_chain.proof_submission_interval = self.proof_submission_interval

            main_chain = self.main_chain
            registered_before = chain_name in main_chain.registered_sub_chains
            pending_before = deepcopy(main_chain.pending_events)
            previous_connection = getattr(
                sub_chain, "main_chain_connection", None
            )
            sync_before = (
                getattr(self.cross_level_sync, "_subchains", {}).get(chain_name)
                if self.cross_level_sync
                else None
            )
            try:
                connected = sub_chain.connect_to_main_chain(main_chain)
            except Exception:
                self._rollback_new_main_chain_registration(
                    chain_name,
                    sub_chain,
                    registered_before,
                    pending_before,
                    previous_connection,
                )
                raise
            if not connected:
                self._rollback_new_main_chain_registration(
                    chain_name,
                    sub_chain,
                    registered_before,
                    pending_before,
                    previous_connection,
                )
                raise RuntimeError(
                    f"Failed to connect sub-chain to main chain: {chain_name}"
                )

            persist_attempted = False
            try:
                if self.cross_level_sync:
                    self.cross_level_sync.connect_subchain(chain_name, sub_chain)
                if persist and self.storage is not None:
                    persist_attempted = True
                    if self.storage.store_chain(sub_chain) is not True:
                        self._rollback_new_main_chain_registration(
                            chain_name,
                            sub_chain,
                            registered_before,
                            pending_before,
                            previous_connection,
                        )
                        self._restore_cross_level_registration(chain_name, sync_before)
                        raise RuntimeError(
                            f"Failed to persist sub-chain metadata: {chain_name}"
                        )
                self.sub_chains[chain_name] = sub_chain
            except Exception:
                if self.sub_chains.get(chain_name) is sub_chain:
                    del self.sub_chains[chain_name]
                self._restore_cross_level_registration(chain_name, sync_before)
                if not persist_attempted:
                    self._rollback_new_main_chain_registration(
                        chain_name,
                        sub_chain,
                        registered_before,
                        pending_before,
                        previous_connection,
                    )
                raise

        # A participant retry failure does not invalidate the successfully
        # connected and persisted sub-chain registration.
        try:
            self.transaction_manager.retry_pending()
        except Exception:
            logger.exception(
                "Sub-chain %s was registered, but pending transaction retries failed",
                chain_name,
            )

    def _restore_cross_level_registration(
        self, chain_name: str, previous: Any | None
    ) -> None:
        """Restore the cross-level mapping after a pre-commit registration failure."""
        if not self.cross_level_sync:
            return
        try:
            if previous is None:
                disconnect = getattr(
                    self.cross_level_sync, "disconnect_subchain", None
                )
                if callable(disconnect):
                    disconnect(chain_name)
            else:
                self.cross_level_sync.connect_subchain(chain_name, previous)
        except Exception:
            logger.exception(
                "Could not restore cross-level registration for %s", chain_name
            )

    def _rollback_new_main_chain_registration(
        self,
        chain_name: str,
        sub_chain: Any,
        registered_before: bool,
        pending_before: list[dict[str, Any]],
        previous_connection: Any | None,
    ) -> None:
        """Undo an unpersisted registration that is still only pending in memory."""
        if registered_before:
            return

        main_chain = self.main_chain
        with main_chain.lock:
            from hierachain.core.utils import get_block_events

            for block in main_chain.chain:
                if any(
                    event.get("event") == "sub_chain_registration"
                    and event.get("entity_id") == chain_name
                    for event in get_block_events(block)
                ):
                    # A concurrent finalization made this registration durable.
                    return

            main_chain.registered_sub_chains.discard(chain_name)
            main_chain.sub_chain_metadata.pop(chain_name, None)
            remove_authority = getattr(main_chain.consensus, "remove_authority", None)
            if callable(remove_authority):
                remove_authority(chain_name)

            new_pending = [
                event
                for event in main_chain.pending_events
                if event not in pending_before
                and event.get("event") == "sub_chain_registration"
                and event.get("entity_id") == chain_name
            ]
            if new_pending:
                main_chain.pending_events[:] = [
                    event
                    for event in main_chain.pending_events
                    if event not in new_pending
                ]
            if getattr(sub_chain, "main_chain_connection", None) is main_chain:
                sub_chain.main_chain_connection = previous_connection

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
