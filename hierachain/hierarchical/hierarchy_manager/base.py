"""
HierarchyManager class — coordinates Main Chain and Sub-Chains.
"""

from __future__ import annotations

import time
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator


_SHARED_POOL = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)


@contextmanager
def _shared_pool(max_workers: int = 8) -> Iterator[ThreadPoolExecutor]:
    yield _SHARED_POOL

from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.multi_org import MultiOrgNetwork
from hierachain.hierarchical.channel import Channel
from hierachain.hierarchical.private_data import PrivateCollection

if TYPE_CHECKING:
    from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.adapters.database.redis_adapter import RedisStorageAdapter
from hierachain.config.settings import settings
from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
from hierachain.cluster.cross_level_sync_types import (
    ConflictResolutionStrategy,
)

from hierachain.hierarchical.hierarchy_manager.validation import (
    _compute_system_integrity_report,
    _validate_cross_chain_consistency,
    _compute_proof_consistency,
)
from hierachain.hierarchical.hierarchy_manager.organization import (
    _trace_entity_history,
    _init_organization_msp,
    _build_channel_orgs,
    _build_collection_orgs,
)

logger = logging.getLogger(__name__)


class HierarchyManager:
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
        self.main_chain: MainChain = MainChain(name)
        self.sub_chains: dict[str, DomainChain] = {}
        self.system_started_at: float = time.time()
        self.node_identity = node_identity

        self.auto_proof_submission: bool = False
        self.proof_submission_interval: int = 60

        self.system_stats: dict[str, Any] = {
            "total_transactions": 0,
            "total_blocks": 0,
            "active_chains": 0,
        }

        self.organizations: dict[str, Any] = {}
        self.network: MultiOrgNetwork | None = None
        self.channels: dict[str, Channel] = {}
        self.private_collections: dict[str, PrivateCollection] = {}

        self.transaction_manager: CrossChainTransactionManager = (
            CrossChainTransactionManager(self)
        )

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

        self.storage = None
        try:
            self.storage = self._create_storage()
            if self.storage is not None:
                self.storage.store_chain(self.main_chain)
        except (IOError, ValueError, RuntimeError) as e:
            logger.error("Failed to initialize storage: %s", e)

    def create_sub_chain(
        self, name: str, domain_type: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        if name in self.sub_chains:
            return False

        from hierachain.domains.chains.domain_chain import DomainChain

        sub_chain = DomainChain(name, domain_type, metadata=metadata)

        if sub_chain.connect_to_main_chain(self.main_chain):
            self.sub_chains[name] = sub_chain
            if self.cross_level_sync:
                self.cross_level_sync.connect_subchain(name, sub_chain)
            return True

        return False

    def get_sub_chain(self, name: str) -> DomainChain | None:
        return self.sub_chains.get(name)

    def get_all_sub_chains(self) -> dict[str, DomainChain]:
        return self.sub_chains

    def get_main_chain(self) -> MainChain:
        return self.main_chain

    def initiate_cross_chain_transaction(
        self, source_chain_name: str, dest_chain_name: str, payload: dict[str, Any],
    ) -> str | None:
        return self.transaction_manager.initiate_transaction(
            source_chain_name, dest_chain_name, payload
        )

    def start_operation(
        self,
        sub_chain_name: str,
        entity_id: str,
        operation_type: str,
        details: dict[str, Any] | None = None
    ) -> bool:
        chain = self.get_sub_chain(sub_chain_name)
        if not chain:
            return False
        return chain.start_domain_operation(entity_id, operation_type, details)

    def complete_operation(
        self,
        sub_chain_name: str,
        entity_id: str,
        operation_type: str,
        result: dict[str, Any] | None = None
    ) -> bool:
        chain = self.get_sub_chain(sub_chain_name)
        if not chain:
            return False
        return chain.complete_operation(entity_id, operation_type, result)

    def submit_proof_to_main_chain(self, sub_chain_name: str) -> bool:
        chain = self.get_sub_chain(sub_chain_name)
        if not chain:
            return False

        result = chain.submit_proof_to_main(self.main_chain)

        if result and self.cross_level_sync:
            sync_result = self.cross_level_sync.sync_to_mainchain(
                sub_chain_name
            )
            if not sync_result.success:
                logger.warning(
                    "Cross-level sync to MainChain failed: %s",
                    sync_result.error_message,
                )

        return result

    def get_system_overview(self) -> dict[str, Any]:
        total_tx = 0
        total_blocks = len(self.main_chain.chain)
        domain_distribution: dict[str, int] = {}

        for chain in self.sub_chains.values():
            stats = chain.get_domain_statistics()
            total_tx += stats.get("total_operations", 0) + stats.get("total_events", 0)
            total_blocks += stats.get("total_blocks", 0)
            d_type = chain.domain_type
            domain_distribution[d_type] = domain_distribution.get(d_type, 0) + 1

        return {
            "uptime_seconds": time.time() - self.system_started_at,
            "total_chains": len(self.sub_chains),
            "main_chain_blocks": len(self.main_chain.chain),
            "total_system_blocks": total_blocks,
            "total_system_transactions": total_tx,
            "domain_distribution": domain_distribution,
        }

    def trace_entity_across_chains(
        self, entity_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        return _trace_entity_history(self.sub_chains, entity_id)

    def get_system_integrity_report(self) -> dict[str, Any]:
        return _compute_system_integrity_report(self)

    def submit_all_proofs(self) -> dict[str, bool]:
        names = list(self.sub_chains.keys())
        results: dict[str, bool] = {}

        with _shared_pool(max_workers=min(len(names), 8)) as pool:
            futures = {
                pool.submit(self.submit_proof_to_main_chain, name): name
                for name in names
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.error("Proof submission failed for %s: %s", name, e)
                    results[name] = False

        return results

    def sync_all_subchains_from_mainchain(self) -> dict[str, dict[str, Any]]:
        names = list(self.sub_chains.keys())
        results: dict[str, dict[str, Any]] = {}

        with _shared_pool(max_workers=min(len(names), 8)) as pool:
            futures = {
                pool.submit(self.cross_level_sync_subchain, name): name
                for name in names
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.error("Sync failed for %s: %s", name, e)
                    results[name] = {"success": False, "error_message": str(e)}

        return results

    def cross_level_sync_subchain(
        self, sub_chain_name: str, from_block: int = 0, to_block: int = -1
    ) -> dict[str, Any]:
        if not self.cross_level_sync:
            return {"success": False, "error_message": "Cross-level sync not enabled"}

        result = self.cross_level_sync.sync_from_mainchain(
            sub_chain_name, from_block, to_block
        )
        return result.to_dict()

    def finalize_main_chain_block(self) -> Any | None:
        if hasattr(self.main_chain, "finalize_block"):
            return self.main_chain.finalize_block()
        return None

    def get_cross_chain_statistics(self) -> dict[str, Any]:
        total_entities = 0
        domain_dist = {}
        for chain in self.sub_chains.values():
            if hasattr(chain, "entity_registry"):
                total_entities += len(chain.entity_registry)
                domain_dist[chain.domain_type] = len(chain.entity_registry)

        return {
            "total_unique_entities": total_entities,
            "cross_chain_operations": 0,
            "total_proofs_submitted": self.main_chain.proof_count,
            "domain_distribution": domain_dist,
        }

    def configure_auto_proof_submission(
        self, enabled: bool, interval: float = 60.0
    ) -> None:
        self.auto_proof_submission = enabled
        self.proof_submission_interval = int(interval)

        for sub_chain in self.sub_chains.values():
            sub_chain.proof_submission_interval = interval

    def execute_system_maintenance(self) -> dict[str, Any]:
        maintenance_results: dict[str, Any] = {
            "timestamp": time.time(), "operations": []
        }
        operations: list[dict[str, Any]] = maintenance_results["operations"]

        proof_results = self.submit_all_proofs()
        operations.append({"operation": "proof_submission", "results": proof_results})

        main_chain_result = self.finalize_main_chain_block()
        if main_chain_result:
            operations.append(
                {"operation": "main_chain_finalization", "result": main_chain_result}
            )

        self.system_stats["system_uptime"] = time.time() - self.system_started_at

        return maintenance_results

    def validate_cross_chain_consistency(self) -> dict[str, Any]:
        return _validate_cross_chain_consistency(self)

    def _check_proof_consistency(self) -> dict[str, Any]:
        return _compute_proof_consistency(self.main_chain, self.sub_chains)

    def create_organization(
        self, org_id: str, name: str, admin_users: list[str] | None = None
    ) -> Any:
        if org_id in self.organizations:
            raise ValueError(f"Organization {org_id} already exists")

        org = _init_organization_msp(org_id, name, admin_users)
        self.organizations[org_id] = org

        if self.network is None:
            self.network = MultiOrgNetwork()

        network = self.network
        if network is not None:
            network.add_organization(org)
        return org

    def get_organization(self, org_id: str) -> Any:
        return self.organizations.get(org_id)

    def create_channel(
        self,
        channel_id: str,
        org_ids: list[str],
        policy_config: dict[str, Any] | None = None,
    ) -> Channel:
        if channel_id in self.channels:
            raise ValueError(f"Channel {channel_id} already exists")

        organizations = _build_channel_orgs(org_ids, self)
        policy = policy_config or {
            "read": "MEMBER",
            "write": "ADMIN",
            "endorsement": "MAJORITY",
        }

        channel = Channel(channel_id, organizations, policy)
        self.channels[channel_id] = channel
        return channel

    def get_channel(self, channel_id: str) -> Channel | None:
        return self.channels.get(channel_id)

    def create_private_collection(
        self,
        name: str,
        org_ids: list[str],
        config: dict[str, Any] | None = None
    ) -> PrivateCollection:
        if name in self.private_collections:
            raise ValueError(f"Private collection {name} already exists")

        organizations = _build_collection_orgs(org_ids, self)
        col_config = config or {
            "block_to_purge": 1000,
            "endorsement_policy": "MAJORITY",
            "min_endorsements": 2,
        }

        private_collection = PrivateCollection(name, organizations, col_config)
        self.private_collections[name] = private_collection
        return private_collection

    def get_private_collection(self, name: str) -> PrivateCollection | None:
        return self.private_collections.get(name)

    def create_private_data_collection(
        self,
        name: str,
        org_ids: list[str],
        config: dict[str, Any] | None = None,
    ) -> PrivateCollection:
        return self.create_private_collection(name, org_ids, config)

    def assign_organization_to_chain(self, org_id: str, chain_name: str) -> bool:
        org = self.get_organization(org_id)
        if not org:
            return False

        chain = self.get_sub_chain(chain_name)
        if not chain:
            return False

        return True

    @staticmethod
    def _create_storage() -> Any | None:
        backend = getattr(settings, "STORAGE_BACKEND", settings.DEFAULT_STORAGE_BACKEND)

        if backend == "sqlite":
            db_path = "hierachain.db"
            if settings.DATABASE_URL.startswith("sqlite:///"):
                db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            return SQLiteAdapter(database_path=db_path)

        if backend in ("postgres", "postgresql"):
            from hierachain.adapters.database.postgres_adapter import PostgresAdapter
            return PostgresAdapter(database_url=settings.DATABASE_URL)

        if backend == "redis":
            return RedisStorageAdapter()

        logger.debug("No persistent storage backend configured (backend=%s)", backend)
        return None

    def set_main_chain(self, main_chain):
        self.main_chain = main_chain

    def add_sub_chain(self, chain_name, sub_chain):
        if chain_name in self.sub_chains:
            raise ValueError(f"Sub-chain {chain_name} already exists")
        self.sub_chains[chain_name] = sub_chain
        sub_chain.connect_to_main_chain(self.main_chain)

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
