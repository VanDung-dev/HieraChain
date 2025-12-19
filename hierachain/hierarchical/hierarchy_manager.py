"""
Hierarchy Manager for HieraChain Framework.

This module provides the HierarchyManager class, which is responsible for
coordinating the interaction between the Main Chain and multiple Sub-Chains
(Domain Chains) in the HieraChain system.
"""

import time
from typing import Optional, Any

from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.multi_org import create_organization, MultiOrgNetwork
from hierachain.hierarchical.channel import Channel, Organization as ChannelOrganization
from hierachain.hierarchical.private_data import PrivateCollection

from hierachain.domains.generic.chains.domain_chain import DomainChain
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager


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
        self.network: Optional[MultiOrgNetwork] = None
        self.channels: dict[str, Channel] = {}
        self.private_collections: dict[str, PrivateCollection] = {}
        
        # Initialize Cross-Chain Transaction Manager
        self.transaction_manager: CrossChainTransactionManager = CrossChainTransactionManager(self)
    
    def create_sub_chain(self, name: str, domain_type: str, 
                        metadata: Optional[dict[str, Any]] = None) -> bool:
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
    
    def get_sub_chain(self, name: str) -> Optional[DomainChain]:
        """Get a sub-chain by name."""
        return self.sub_chains.get(name)

    def get_all_sub_chains(self) -> dict[str, DomainChain]:
        """Get all sub-chains."""
        return self.sub_chains
        
    def get_main_chain(self) -> MainChain:
        """Get the main chain instance."""
        return self.main_chain
        
    def initiate_cross_chain_transaction(self, source_chain_name: str, dest_chain_name: str,
                                        payload: dict[str, Any]) -> Optional[str]:
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
                       operation_type: str, details: Optional[dict[str, Any]] = None) -> bool:
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

        # In a real implementation:
        # 1. Generate Merkle proof of current state
        # 2. Submit to Main Chain
        # 3. Main Chain verifies signatures and previous hash linkage
        
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
            "uptime": time.time() - self.system_started_at,
            "total_chains": len(self.sub_chains) + 1,  # +1 for MainChain
            "total_transactions_system_wide": total_tx,
            "total_blocks_system_wide": total_blocks,
            "domain_types": domain_distribution,
            "main_chain_height": len(self.main_chain.chain)
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

    def finalize_main_chain_block(self) -> Optional[Any]:
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
        
        Returns:
            Consistency validation results
        """
        validation_results = {
            "timestamp": time.time(),
            "main_chain_valid": self.main_chain.is_chain_valid(),
            "sub_chain_validation": {},
            "proof_consistency": {},
            "overall_consistent": True
        }
        
        # Validate each Sub-Chain
        for sub_chain_name, sub_chain in self.sub_chains.items():
            is_valid = sub_chain.is_chain_valid()
            validation_results["sub_chain_validation"][sub_chain_name] = is_valid
            
            if not is_valid:
                validation_results["overall_consistent"] = False
        
        # Check proof consistency
        for sub_chain_name, sub_chain in self.sub_chains.items():
            if len(sub_chain.chain) > 1:  # Has blocks beyond genesis
                latest_block = sub_chain.get_latest_block()
                proof_exists = self.main_chain.verify_proof(
                    latest_block.hash, sub_chain_name)
                validation_results["proof_consistency"][sub_chain_name] = proof_exists
        
        return validation_results

    def create_organization(self, org_id: str, name: str, admin_users: list[str] = None) -> Any:
        """
        Create an organization with MSP configuration (0.dev3 feature).
        
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
        Get organization by ID (0.dev3 feature).
        
        Args:
            org_id: Organization ID
            
        Returns:
            Organization object or None if not found
        """
        return self.organizations.get(org_id)
    
    def create_channel(self, channel_id: str, org_ids: list[str], policy_config: dict[str, Any] = None) -> Channel:
        """
        Create a channel for secure data isolation (0.dev3 feature).
        
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
    
    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """
        Get channel by ID (0.dev3 feature).
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Channel object or None if not found
        """
        return self.channels.get(channel_id)
    
    def create_private_collection(self, name: str, org_ids: list[str], config: dict[str, Any] = None) -> PrivateCollection:
        """
        Create a private data collection (0.dev3 feature).
        
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
    
    def get_private_collection(self, name: str) -> Optional[PrivateCollection]:
        """
        Get private data collection by name (0.dev3 feature).
        
        Args:
            name: Collection name
            
        Returns:
            Private collection object or None if not found
        """
        return self.private_collections.get(name)
    
    def assign_organization_to_chain(self, org_id: str, chain_name: str) -> bool:
        """
        Assign an organization to a chain (0.dev3 feature).
        
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
