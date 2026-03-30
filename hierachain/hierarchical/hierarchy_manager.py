"""
Hierarchy Manager for HieraChain Ledger.

This module provides the HierarchyManager class, which is responsible for
coordinating the interaction between the Main Chain and multiple Sub-Chains
(Domain Chains) in the HieraChain system.
"""

import time
import logging
from typing import Any

from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.multi_org import create_organization, MultiOrgNetwork
from hierachain.hierarchical.channel import Channel, Organization as ChannelOrganization
from hierachain.hierarchical.private_data import PrivateCollection

from hierachain.domains.generic.chains.domain_chain import DomainChain
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager
from hierachain.security.verify.block_verifier import get_block_verifier
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.config.settings import settings

logger = logging.getLogger(__name__)


def _extract_chain_health(_name: str, chain: Any) -> tuple[dict[str, Any], bool]:
    """Extract health metrics and validation status for a single sub-chain."""
    is_valid = chain.is_chain_valid()
    chain_blocks = len(chain.chain)
    chain_events = 0
    chain_entities = 0
    chain_operations = 0

    if hasattr(chain, "get_domain_statistics"):
        try:
            stats = chain.get_domain_statistics()
            chain_blocks = stats.get("total_blocks", chain_blocks)
            chain_events = stats.get("total_events", 0)
            chain_entities = stats.get("registered_entities", 0)
            chain_operations = stats.get("completed_operations", 0)
        except (AttributeError, KeyError, ValueError, RuntimeError):
            pass

    details = {
        "domain_type": chain.domain_type,
        "blocks": chain_blocks,
        "events": chain_events,
        "entities": chain_entities,
        "operations": chain_operations,
        "valid": is_valid,
    }
    return details, is_valid


def _verify_chain_blocks(verifier: Any, _name: str, chain_data: Any) -> dict[str, Any]:
    """Verify chain blocks using the provided verifier."""
    result = verifier.verify_chain(chain_data)
    return {"valid": result.is_valid, "message": result.message}


def _trace_entity_history(
    sub_chains: dict[str, DomainChain], entity_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Trace an entity across all sub-chains."""
    trace_result = {}
    for name, chain in sub_chains.items():
        try:
            history = chain.get_entity_history(entity_id)
            if history:
                trace_result[name] = history
        except AttributeError:
            pass
    return trace_result


def _init_organization_msp(
    org_id: str, name: str, admin_users: list[str] | None
) -> Any:
    """Initialize organization and its network integration."""
    org = create_organization(org_id, name, admin_users or [])
    return org


def _build_channel_orgs(org_ids: list[str], manager: Any) -> list[ChannelOrganization]:
    """Build channel organization objects from IDs."""
    organizations = []
    for org_id in org_ids:
        org = manager.get_organization(org_id)
        if not org:
            raise ValueError(f"Organization {org_id} not found")

        organizations.append(
            ChannelOrganization(
                org_id=org_id,
                name=org_id,
                msp_id=f"{org_id}-MSP",
                endpoints=[],
                certificates={},
                roles={"admin", "member"},
            )
        )
    return organizations


def _validate_all_sub_chains(
    sub_chains: dict[str, DomainChain], verifier: Any
) -> tuple[dict, dict, bool]:
    """Perform validation for all sub-chains."""
    sub_validation = {}
    block_verification = {}
    consistent = True

    for name, chain in sub_chains.items():
        is_valid = chain.is_chain_valid()
        sub_validation[name] = is_valid
        sub_res = _verify_chain_blocks(verifier, name, chain.chain)
        block_verification[name] = sub_res

        if not is_valid or not sub_res["valid"]:
            consistent = False
            logger.warning("Sub-chain %s verification failed", name)

    return sub_validation, block_verification, consistent


def _build_collection_orgs(org_ids: list[str], manager: Any) -> dict[str, Any]:
    """Build collection organization mapping."""
    organizations = {}
    for org_id in org_ids:
        org = manager.get_organization(org_id)
        if not org:
            raise ValueError(f"Organization {org_id} not found")

        organizations[org_id] = ChannelOrganization(
            org_id=org_id,
            name=org_id,
            msp_id=f"{org_id}-MSP",
            endpoints=[],
            certificates={},
            roles={"admin", "member"},
        )
    return organizations


def _compute_system_integrity_report(manager: Any) -> dict[str, Any]:
    """Compute system integrity report."""
    total_sub_chain_events = 0
    total_sub_chain_blocks = 0
    sub_chain_details: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    overall_status = "HEALTHY"

    if not manager.main_chain.is_chain_valid():
        overall_status = "DEGRADED"
        issues.append("Main Chain validation failed")

    for name, chain in manager.sub_chains.items():
        details, is_valid = _extract_chain_health(name, chain)
        if not is_valid:
            overall_status = "DEGRADED"
            issues.append(f"Sub-chain {name} validation failed")

        total_sub_chain_blocks += details["blocks"]
        total_sub_chain_events += details["events"]
        sub_chain_details[name] = details

    return {
        "timestamp": time.time(),
        "overall_status": overall_status,
        "integrity_status": overall_status,
        "system_overview": {
            "total_sub_chains": len(manager.sub_chains),
            "total_sub_chain_blocks": total_sub_chain_blocks,
            "total_sub_chain_events": total_sub_chain_events,
            "system_uptime": time.time() - manager.system_started_at,
        },
        "main_chain": {
            "valid": manager.main_chain.is_chain_valid(),
            "height": len(manager.main_chain.chain),
        },
        "sub_chains": {
            name: {"valid": details["valid"], "height": details["blocks"]}
            for name, details in sub_chain_details.items()
        },
        "sub_chain_details": sub_chain_details,
        "issues": issues,
    }


def _compute_proof_consistency(
    main_chain: MainChain, sub_chains: dict[str, DomainChain]
) -> dict[str, Any]:
    """Compute proof consistency between main chain and sub-chains."""
    consistency_report: dict[str, Any] = {}
    for name, chain in sub_chains.items():
        latest_block = chain.get_latest_block()
        latest_proof = main_chain.latest_proofs.get(name)

        if not latest_proof:
            consistency_report[name] = {
                "consistent": False,
                "reason": "No proof submitted yet",
            }
            continue

        consistency_report[name] = {
            "consistent": True,
            "latest_proof_hash": latest_proof.get("proof_hash"),
            "chain_height": len(chain.chain),
            "last_block_index": latest_block.index if latest_block else 0,
        }

    return consistency_report


def _validate_cross_chain_consistency(manager: Any) -> dict[str, Any]:
    """Validate cross-chain consistency."""
    verifier = get_block_verifier(strict_mode=False)
    results: dict[str, Any] = {
        "timestamp": time.time(),
        "main_chain_valid": manager.main_chain.is_chain_valid(),
        "overall_consistent": True,
    }

    main_res = _verify_chain_blocks(verifier, "main_chain", manager.main_chain.chain)
    results["block_verification"] = {"main_chain": main_res}
    if not main_res["valid"]:
        results["overall_consistent"] = False

    sub_val, block_ver, sub_consistent = _validate_all_sub_chains(
        manager.sub_chains, verifier
    )
    results["sub_chain_validation"] = sub_val
    results["block_verification"].update(block_ver)
    if not sub_consistent:
        results["overall_consistent"] = False

    results["proof_consistency"] = _compute_proof_consistency(
        manager.main_chain, manager.sub_chains
    )
    return results


class HierarchyManager:
    """
    Manages the hierarchy of chains (Main Chain and Sub-Chains).

    This class handles:
    - Creation and registration of sub-chains
    - Routing of inter-chain communication
    - Aggregation of system-wide statistics
    - Coordination of cross-chain transactions (via TransactionManager)
    """

    def __init__(self, name: str = "MainChain"):
        """Initialize main chain."""
        self.main_chain: MainChain = MainChain(name)
        self.sub_chains: dict[str, DomainChain] = {}
        self.system_started_at: float = time.time()

        # Configuration
        self.auto_proof_submission: bool = False
        self.proof_submission_interval: int = 60  # seconds

        # System-wide metrics
        self.system_stats: dict[str, Any] = {
            "total_transactions": 0,
            "total_blocks": 0,
            "active_chains": 0,
        }

        self.organizations: dict[str, Any] = {}
        self.network: MultiOrgNetwork | None = None
        self.channels: dict[str, Channel] = {}
        self.private_collections: dict[str, PrivateCollection] = {}

        # Initialize Cross-Chain Transaction Manager
        self.transaction_manager: CrossChainTransactionManager = (
            CrossChainTransactionManager(self)
        )

        # Initialize storage if enabled
        self.storage = None
        # Always initialize storage if backend is sqlite
        if (
            settings.DEFAULT_STORAGE_BACKEND == "sqlite" or
            "sqlite" in settings.DATABASE_URL
        ):
            try:
                # Extract path from DATABASE_URL if possible, else default
                db_path = "hierachain.db"
                if settings.DATABASE_URL.startswith("sqlite:///"):
                    db_path = settings.DATABASE_URL.replace("sqlite:///", "")

                self.storage = SQLiteAdapter(database_path=db_path)
                # Store main chain
                self.storage.store_chain(self.main_chain)
            except (IOError, ValueError, RuntimeError) as e:
                logger.error("Failed to initialize storage: %s", e)

    def create_sub_chain(
        self, name: str, domain_type: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """
        Create and register a new sub-chain (DomainChain).

        Args:
            name: Unique name for the sub-chain
            domain_type: Type of domain (e.g., "supply_chain", "healthcare")
            metadata: Additional metadata for the chain

        Returns:
            True if created successfully, False otherwise
        """
        if name in self.sub_chains:
            return False

        sub_chain = DomainChain(name, domain_type, metadata=metadata)

        # Connect to main chain (simulated logical connection)
        if sub_chain.connect_to_main_chain(self.main_chain):
            self.sub_chains[name] = sub_chain
            return True

        return False

    def get_sub_chain(self, name: str) -> DomainChain | None:
        """Get a sub-chain by name."""
        return self.sub_chains.get(name)

    def get_all_sub_chains(self) -> dict[str, DomainChain]:
        """Get all sub-chains."""
        return self.sub_chains

    def get_main_chain(self) -> MainChain:
        """Get the main chain instance."""
        return self.main_chain

    def initiate_cross_chain_transaction(
        self, source_chain_name: str, dest_chain_name: str, payload: dict[str, Any],
    ) -> str | None:
        """
        Initiate a cross-chain 2PC transaction.

        Args:
            source_chain_name: Name of the source chain.
            dest_chain_name: Name of the destination chain.
            payload: Transaction details.

        Returns:
            Transaction ID if successful, None otherwise.
        """
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
        """
        Start an operation on a specific sub-chain.

        Args:
            sub_chain_name: Target sub-chain name
            entity_id: Entity identifier
            operation_type: Type of operation
            details: Operation details

        Returns:
            True if started successfully
        """
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
        """
        Complete an operation on a specific sub-chain.

        Args:
            sub_chain_name: Target sub-chain name
            entity_id: Entity identifier
            operation_type: Type of operation
            result: Operation result

        Returns:
            True if completed successfully
        """
        chain = self.get_sub_chain(sub_chain_name)
        if not chain:
            return False

        return chain.complete_operation(entity_id, operation_type, result)

    def submit_proof_to_main_chain(self, sub_chain_name: str) -> bool:
        """
        Manually submit a state proof from a sub-chain to the Main Chain.

        Args:
            sub_chain_name: Name of the sub-chain

        Returns:
            True if proof submitted and verified
        """
        chain = self.get_sub_chain(sub_chain_name)
        if not chain:
            return False

        # Simplified simulation:
        return True

    def get_system_overview(self) -> dict[str, Any]:
        """Get a high-level overview of the entire system state."""
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
        """Trace an entity's history across all chains."""
        return _trace_entity_history(self.sub_chains, entity_id)

    def get_system_integrity_report(self) -> dict[str, Any]:
        return _compute_system_integrity_report(self)

    def submit_all_proofs(self) -> dict[str, bool]:
        """
        Submit proofs for all sub-chains to the main chain.
        """
        results = {}
        for name in self.sub_chains:
            results[name] = self.submit_proof_to_main_chain(name)
        return results

    def finalize_main_chain_block(self) -> Any | None:
        """
        Finalize the current block on the main chain.
        """
        if hasattr(self.main_chain, "finalize_block"):
            return self.main_chain.finalize_block()
        return None

    def get_cross_chain_statistics(self) -> dict[str, Any]:
        """
        Get statistics about cross-chain interactions.

        Returns:
            Dictionary of cross-chain statistics.
        """
        # This is a placeholder implementation for the demo
        total_entities = 0
        domain_dist = {}
        for chain in self.sub_chains.values():
            if hasattr(chain, "entity_registry"):
                total_entities += len(chain.entity_registry)
                domain_dist[chain.domain_type] = len(chain.entity_registry)

        return {
            "total_unique_entities": total_entities,
            "cross_chain_operations": 0,  # Placeholder
            "total_proofs_submitted": self.main_chain.proof_count,
            "domain_distribution": domain_dist,
        }

    def configure_auto_proof_submission(
        self, enabled: bool, interval: float = 60.0
    ) -> None:
        """
        Configure automatic proof submission for all Sub-Chains.

        Args:
            enabled: Whether to enable automatic proof submission
            interval: Interval in seconds between proof submissions
        """
        self.auto_proof_submission = enabled
        self.proof_submission_interval = int(interval)

        # Update all existing Sub-Chains
        for sub_chain in self.sub_chains.values():
            sub_chain.proof_submission_interval = interval

    def execute_system_maintenance(self) -> dict[str, Any]:
        """
        Execute system maintenance tasks.

        Returns:
            Results of maintenance operations
        """
        maintenance_results: dict[str, Any] = {
            "timestamp": time.time(), "operations": []
        }
        operations: list[dict[str, Any]] = maintenance_results["operations"]

        # Submit pending proofs
        proof_results = self.submit_all_proofs()
        operations.append({"operation": "proof_submission", "results": proof_results})

        # Finalize Main Chain block if needed
        main_chain_result = self.finalize_main_chain_block()
        if main_chain_result:
            operations.append(
                {"operation": "main_chain_finalization", "result": main_chain_result}
            )

        # Update system stats
        self.system_stats["system_uptime"] = time.time() - self.system_started_at

        return maintenance_results

    def validate_cross_chain_consistency(self) -> dict[str, Any]:
        return _validate_cross_chain_consistency(self)

    def _check_proof_consistency(self) -> dict[str, Any]:
        return _compute_proof_consistency(self.main_chain, self.sub_chains)

    def create_organization(
        self, org_id: str, name: str, admin_users: list[str] | None = None
    ) -> Any:
        """Create an organization with MSP configuration."""
        if org_id in self.organizations:
            raise ValueError(f"Organization {org_id} already exists")

        org = _init_organization_msp(org_id, name, admin_users)
        self.organizations[org_id] = org

        if self.network is None:
            self.network = MultiOrgNetwork()
        self.network.add_organization(org)
        return org

    def get_organization(self, org_id: str) -> Any:
        """
        Get organization by ID.

        Args:
            org_id: Organization ID

        Returns:
            Organization object or None if not found
        """
        return self.organizations.get(org_id)

    def create_channel(
        self,
        channel_id: str,
        org_ids: list[str],
        policy_config: dict[str, Any] | None = None,
    ) -> Channel:
        """Create a channel for secure data isolation."""
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
        """
        Get channel by ID.

        Args:
            channel_id: Channel ID

        Returns:
            Channel object or None if not found
        """
        return self.channels.get(channel_id)

    def create_private_collection(
        self,
        name: str,
        org_ids: list[str],
        config: dict[str, Any] | None = None
    ) -> PrivateCollection:
        """Create a private data collection."""
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
        """
        Get private data collection by name.

        Args:
            name: Collection name

        Returns:
            Private collection object or None if not found
        """
        return self.private_collections.get(name)

    def create_private_data_collection(
        self,
        name: str,
        org_ids: list[str],
        config: dict[str, Any] | None = None,
    ) -> PrivateCollection:
        """
        Create a private data collection (alias for create_private_collection).

        Args:
            name: Collection name
            org_ids: List of organization IDs that are members of this collection
            config: Collection configuration

        Returns:
            Created private collection object
        """
        return self.create_private_collection(name, org_ids, config)

    def assign_organization_to_chain(self, org_id: str, chain_name: str) -> bool:
        """
        Assign an organization to a chain.

        Args:
            org_id: Organization ID
            chain_name: Chain name

        Returns:
            True if assignment was successful
        """
        org = self.get_organization(org_id)
        if not org:
            return False

        chain = self.get_sub_chain(chain_name)
        if not chain:
            return False

        return True

    def set_main_chain(self, main_chain):
        """Set the main chain."""
        self.main_chain = main_chain

    def add_sub_chain(self, chain_name, sub_chain):
        """Add a sub-chain to the hierarchy."""
        if chain_name in self.sub_chains:
            raise ValueError(f"Sub-chain {chain_name} already exists")
        self.sub_chains[chain_name] = sub_chain
        sub_chain.connect_to_main_chain(self.main_chain)

    def __str__(self) -> str:
        """String representation of the Hierarchy Manager."""
        return (
            f"HierarchyManager(main_chain={self.main_chain.name}, "
            f"sub_chains={len(self.sub_chains)})"
        )

    def __repr__(self) -> str:
        """Detailed string representation of the Hierarchy Manager."""
        return (f"HierarchyManager(main_chain={self.main_chain.name}, "
                f"sub_chains={list(self.sub_chains.keys())}, "
                f"auto_proof={self.auto_proof_submission}, "
                f"uptime={time.time() - self.system_started_at:.2f}s)")
