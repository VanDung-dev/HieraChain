"""
HierarchyManager class — coordinates Main Chain and Sub-Chains.

Behavior is composed from responsibility-specific mixins:
    - ``ChainOperationsMixin``        - sub-chain creation and registration
    - ``OrganizationOperationsMixin`` - organizations, channels, access control
    - ``StateOperationsMixin``        - durable registry and recovery state
    - ``SystemOperationsMixin``       - system reports and maintenance
    - ``TransactionCoordinationMixin`` - cross-chain coordinator plumbing
"""

from __future__ import annotations

import threading
import time
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any

from hierachain.hierarchical.hierarchy_manager import bootstrap, storage_factory
from hierachain.hierarchical.hierarchy_manager.chain_ops import ChainOperationsMixin
from hierachain.hierarchical.hierarchy_manager.org_ops import (
    OrganizationOperationsMixin,
)
from hierachain.hierarchical.hierarchy_manager.state_ops import StateOperationsMixin
from hierachain.hierarchical.hierarchy_manager.system_ops import SystemOperationsMixin
from hierachain.hierarchical.hierarchy_manager.transaction_ops import (
    TransactionCoordinationMixin,
)
from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.multi_org import MultiOrgNetwork
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager

if TYPE_CHECKING:
    from hierachain.domains.chains.domain_chain import DomainChain
    from hierachain.hierarchical.channel import Channel


class HierarchyManager(
    ChainOperationsMixin,
    OrganizationOperationsMixin,
    StateOperationsMixin,
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

        bootstrap.initialize(self, node_identity)

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
