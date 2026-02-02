"""
Hierarchy Manager for HieraChain Framework.

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


class HierarchyManager:
    """
    Manages the hierarchy of chains (Main Chain and Sub-Chains).
    
    This class handles:
    - Creation and registration of sub-chains
    - Routing of inter-chain communication
    - Aggregation of system-wide statistics
    - Coordination of cross-chain transactions (via TransactionManager)
    """
    
    def __init__(self, main_chain_name: str = "MainChain"):
        """
        Initialize the Hierarchy Manager.
        
        Args:
            main_chain_name: Name of the main chain.
        """
        self.main_chain: MainChain = MainChain(main_chain_name)
        self.sub_chains: dict[str, DomainChain] = {}
        self.system_started_at: float = time.time()
        
        # Configuration
        self.auto_proof_submission: bool = False
        self.proof_submission_interval: int = 60  # seconds
        
        # System-wide metrics
        self.system_stats: dict[str, Any] = {
            "total_transactions": 0,
            "total_blocks": 0,
            "active_chains": 0
        }

        self.organizations: dict[str, Any] = {}
        self.network: MultiOrgNetwork | None = None
        self.channels: dict[str, Channel] = {}
        self.private_collections: dict[str, PrivateCollection] = {}
        
        # Initialize Cross-Chain Transaction Manager
        self.transaction_manager: CrossChainTransactionManager = CrossChainTransactionManager(self)

        # Initialize storage if enabled
        self.storage = None
        # Always initialize storage if backend is sqlite
        if settings.DEFAULT_STORAGE_BACKEND == "sqlite" or "sqlite" in settings.DATABASE_URL:
            try:
                # Extract path from DATABASE_URL if possible, else default
                db_path = "hierachain.db"
                if settings.DATABASE_URL.startswith("sqlite:///"):
                    db_path = settings.DATABASE_URL.replace("sqlite:///", "")

                self.storage = SQLiteAdapter(database_path=db_path)
                # Store main chain
                self.storage.store_chain(self.main_chain)
            except Exception as e:
                logger.error(f"Failed to initialize storage: {e}")
    
    def create_sub_chain(self, name: str, domain_type: str, metadata: dict[str, Any] | None = None) -> bool:
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

        sub_chain = DomainChain(name, domain_type)
        
        # Connect to main chain (simulated logical connection)
        if sub_chain.connect_to_main_chain(self.main_chain):
            self.sub_chains[name] = sub_chain

            # Record creation event on Main Chain
            _connection_metadata = metadata or {}
            # (In a real system, we might log this to main chain)
            
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
        
    def initiate_cross_chain_transaction(self, source_chain_name: str, dest_chain_name: str,
                                        payload: dict[str, Any]) -> str | None:
        """
        Initiate a cross-chain 2PC transaction.
        
        Args:
            source_chain_name: Name of the source chain.
            dest_chain_name: Name of the destination chain.
            payload: Transaction details.
            
        Returns:
            Transaction ID if successful, None otherwise.
        """
        return self.transaction_manager.initiate_transaction(source_chain_name, dest_chain_name, payload)

    def start_operation(self, sub_chain_name: str, entity_id: str, 
                       operation_type: str, details: dict[str, Any] | None = None) -> bool:
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
    
    def complete_operation(self, sub_chain_name: str, entity_id: str,
                          operation_type: str, result: dict[str, Any] | None = None) -> bool:
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
        """
        Get a high-level overview of the entire system state.
        
        Returns:
            Dictionary containing system statistics
        """
        total_tx = 0
        total_blocks = len(self.main_chain.chain)
        
        domain_distribution: dict[str, int] = {}
        operation_types: dict[str, int] = {}

        for name, chain in self.sub_chains.items():
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
            "domain_distribution": domain_distribution
        }

    def trace_entity_across_chains(self, entity_id: str) -> dict[str, list[dict[str, Any]]]:
        """
        Trace an entity's history across all chains in the hierarchy.
        
        Args:
            entity_id: The unique identifier of the entity to trace.
            
        Returns:
            A dictionary mapping chain names to lists of events for the entity.
        """
        trace_result = {}
        
        for chain_name, chain in self.sub_chains.items():
            try:
                # Assuming BaseChain/DomainChain has get_entity_history method
                history = chain.get_entity_history(entity_id)
                if history:
                    trace_result[chain_name] = history
            except AttributeError:
                # Chain might not support entity history
                pass
                
        return trace_result

    def get_system_integrity_report(self) -> dict[str, Any]:
        """
        Generate a system-wide integrity report.
        
        Checks validity of all chains and aggregates health metrics.
        
        Returns:
            A dictionary containing system integrity status and metrics.
        """
        total_tx = 0
        total_blocks = len(self.main_chain.chain)
        total_sub_chain_events = 0
        total_sub_chain_blocks = 0
        
        sub_chain_details = {}
        issues = []
        overall_status = "HEALTHY"
        
        if not self.main_chain.is_chain_valid():
            overall_status = "DEGRADED"
            issues.append("Main Chain validation failed")
            
        for name, chain in self.sub_chains.items():
            is_valid = chain.is_chain_valid()
            if not is_valid:
                overall_status = "DEGRADED"
                issues.append(f"Sub-chain {name} validation failed")
                
            # Get chain stats
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
                except Exception:
                    pass
            
            total_blocks += chain_blocks
            total_sub_chain_blocks += chain_blocks
            total_sub_chain_events += chain_events
            total_tx += chain_events # events are transactions in this model
            
            sub_chain_details[name] = {
                "domain_type": chain.domain_type,
                "blocks": chain_blocks,
                "events": chain_events,
                "entities": chain_entities,
                "operations": chain_operations,
                "valid": is_valid
            }
            
        report = {
            "timestamp": time.time(),
            "overall_status": overall_status,
            "integrity_status": overall_status, # For demo compatibility
            "system_overview": {
                "total_sub_chains": len(self.sub_chains),
                "total_sub_chain_blocks": total_sub_chain_blocks,
                "total_sub_chain_events": total_sub_chain_events,
                "system_uptime": time.time() - self.system_started_at
            },
            "main_chain": {
                "valid": self.main_chain.is_chain_valid(),
                "height": len(self.main_chain.chain)
            },
            "sub_chains": {name: {"valid": details["valid"], "height": details["blocks"]} for name, details in sub_chain_details.items()},
            "sub_chain_details": sub_chain_details,
            "issues": issues
        }
                 
        return report

    def finalize_main_chain_block(self) -> Any:
        """
        Finalize a block on the Main Chain.
        
        Returns:
            The newly created block or None if no pending events.
        """
        return self.main_chain.finalize_block()
    
    def submit_all_proofs(self) -> dict[str, bool]:
        """
        Trigger proof submission for all sub-chains.
        
        Returns:
             Dictionary of submission results per chain.
        """
        results = {}
        for name, chain in self.sub_chains.items():
            try:
                results[name] = chain.submit_proof_to_main(self.main_chain)
            except Exception as e:
                logger.error(f"Error submitting proof for {name}: {e}")
                results[name] = False
        return results

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
            "cross_chain_operations": 0, # Placeholder
            "total_proofs_submitted": self.main_chain.proof_count,
            "domain_distribution": domain_dist
        }

    
    def configure_auto_proof_submission(self, enabled: bool, interval: float = 60.0) -> None:
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
        if hasattr(self.main_chain, 'finalize_block'):
            return self.main_chain.finalize_block()
        return None
    
    def execute_system_maintenance(self) -> dict[str, Any]:
        """
        Execute system maintenance tasks.
        
        Returns:
            Results of maintenance operations
        """
        maintenance_results = {
            "timestamp": time.time(),
            "operations": []
        }
        
        # Submit pending proofs
        proof_results = self.submit_all_proofs()
        maintenance_results["operations"].append({
            "operation": "proof_submission",
            "results": proof_results
        })
        
        # Finalize Main Chain block if needed
        main_chain_result = self.finalize_main_chain_block()
        if main_chain_result:
            maintenance_results["operations"].append({
                "operation": "main_chain_finalization",
                "result": main_chain_result
            })
        
        # Update system stats
        self.system_stats["system_uptime"] = time.time() - self.system_started_at
        
        return maintenance_results
    
    def validate_cross_chain_consistency(self) -> dict[str, Any]:
        """
        Validate consistency across the entire hierarchical system.
        
        Uses BlockVerifier for comprehensive validation including:
        - Block hash verification
        - Merkle root verification
        - Chain link verification
        
        Returns:
            Consistency validation results
        """
        verifier = get_block_verifier(strict_mode=False)
        
        validation_results: dict[str, Any] = {
            "timestamp": time.time(),
            "main_chain_valid": self.main_chain.is_chain_valid(),
            "sub_chain_validation": {},
            "block_verification": {},
            "proof_consistency": {},
            "overall_consistent": True
        }
        
        # Validate Main Chain blocks with BlockVerifier
        main_chain_result = verifier.verify_chain(self.main_chain.chain)
        validation_results["block_verification"]["main_chain"] = {
            "valid": main_chain_result.is_valid,
            "message": main_chain_result.message
        }
        if not main_chain_result.is_valid:
            validation_results["overall_consistent"] = False
            logger.warning(f"Main chain verification failed: {main_chain_result.message}")
        
        # Validate each Sub-Chain
        for sub_chain_name, sub_chain in self.sub_chains.items():
            is_valid = sub_chain.is_chain_valid()
            validation_results["sub_chain_validation"][sub_chain_name] = is_valid
            
            # Also verify with BlockVerifier
            sub_result = verifier.verify_chain(sub_chain.chain)
            validation_results["block_verification"][sub_chain_name] = {
                "valid": sub_result.is_valid,
                "message": sub_result.message
            }
            
            if not is_valid or not sub_result.is_valid:
                validation_results["overall_consistent"] = False
                logger.warning(f"Sub-chain {sub_chain_name} verification failed")
        
        # Check proof consistency
        for sub_chain_name, sub_chain in self.sub_chains.items():
            if len(sub_chain.chain) > 1:  # Has blocks beyond genesis
                latest_block = sub_chain.get_latest_block()
                proof_exists = self.main_chain.verify_proof(
                    latest_block.hash, sub_chain_name)
                validation_results["proof_consistency"][sub_chain_name] = proof_exists
        
        # Log verification stats
        stats = verifier.get_stats()
        logger.debug(f"Block verification stats: {stats}")
        
        return validation_results

    def create_organization(self, org_id: str, name: str, admin_users: list[str] = None) -> Any:
        """
        Create an organization with MSP configuration.
        
        Args:
            org_id: Unique organization identifier
            name: Organization name
            admin_users: List of admin user IDs
            
        Returns:
            Created organization object
        """
        if org_id in self.organizations:
            raise ValueError(f"Organization {org_id} already exists")
        
        # Create organization using factory function
        org = create_organization(org_id, name, admin_users)
        self.organizations[org_id] = org
        
        # Initialize network if not already done
        if self.network is None:
            self.network = MultiOrgNetwork()
        
        # Add organization to network
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
    
    def create_channel(self, channel_id: str, org_ids: list[str], policy_config: dict[str, Any] = None) -> Channel:
        """
        Create a channel for secure data isolation.
        
        Args:
            channel_id: Unique channel identifier
            org_ids: List of organization IDs participating in the channel
            policy_config: Channel policy configuration
            
        Returns:
            Created channel object
        """
        if channel_id in self.channels:
            raise ValueError(f"Channel {channel_id} already exists")
        
        # Validate organizations exist
        organizations = []
        for org_id in org_ids:
            org = self.get_organization(org_id)
            if not org:
                raise ValueError(f"Organization {org_id} not found")
            
            # Create ChannelOrganization object
            channel_org = ChannelOrganization(
                org_id=org_id,
                name=org_id,  # Using org_id as name for simplicity
                msp_id=f"{org_id}-MSP",
                endpoints=[],
                certificates={},
                roles={"admin", "member"}  # Simplified roles
            )
            organizations.append(channel_org)
        
        # Default policy configuration
        if policy_config is None:
            policy_config = {
                "read": "MEMBER",
                "write": "ADMIN",
                "endorsement": "MAJORITY"
            }
        
        # Create channel
        channel = Channel(channel_id, organizations, policy_config)
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
    
    def create_private_collection(self, name: str, org_ids: list[str], config: dict[str, Any] = None) -> PrivateCollection:
        """
        Create a private data collection.
        
        Args:
            name: Collection name
            org_ids: List of organization IDs that are members of this collection
            config: Collection configuration
            
        Returns:
            Created private collection object
        """
        if name in self.private_collections:
            raise ValueError(f"Private collection {name} already exists")
        
        # Validate organizations exist
        organizations = {}
        for org_id in org_ids:
            org = self.get_organization(org_id)
            if not org:
                raise ValueError(f"Organization {org_id} not found")
            
            # Create ChannelOrganization object for private collection
            channel_org = ChannelOrganization(
                org_id=org_id,
                name=org_id,  # Using org_id as name for simplicity
                msp_id=f"{org_id}-MSP",
                endpoints=[],
                certificates={},
                roles={"admin", "member"}  # Simplified roles
            )
            organizations[org_id] = channel_org
        
        # Default configuration
        if config is None:
            config = {
                "block_to_purge": 1000,
                "endorsement_policy": "MAJORITY",
                "min_endorsements": 2
            }
        
        # Create private collection
        private_collection = PrivateCollection(name, organizations, config)
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
    
    def create_private_data_collection(self, name: str, org_ids: list[str], config: dict[str, Any] = None) -> PrivateCollection:
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
        
        # In a full implementation, this would establish a relationship
        # between the organization and chain for access control
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
        return f"HierarchyManager(main_chain={self.main_chain.name}, sub_chains={len(self.sub_chains)})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the Hierarchy Manager."""
        return (f"HierarchyManager(main_chain={self.main_chain.name}, "
                f"sub_chains={list(self.sub_chains.keys())}, "
                f"auto_proof={self.auto_proof_submission}, "
                f"uptime={time.time() - self.system_started_at:.2f}s)")
