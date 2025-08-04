"""
Hierarchy Manager for Hierarchical-Blockchain Framework.

This module implements the HierarchyManager class that coordinates and manages
the relationships between Main Chain and Sub-Chains, providing orchestration
capabilities for the entire hierarchical blockchain system.
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable
from .main_chain import MainChain
from .sub_chain import SubChain
from core.utils import sanitize_metadata_for_main_chain


class HierarchyManager:
    """
    Hierarchy Manager for coordinating Main Chain and Sub-Chains.
    
    The HierarchyManager acts as the orchestrator of the hierarchical system:
    - Manages Main Chain and Sub-Chain lifecycle
    - Coordinates proof submissions between chains
    - Provides system-wide monitoring and integrity checks
    - Handles cross-chain communication and validation
    """
    
    def __init__(self, main_chain_name: str = "MainChain"):
        """
        Initialize the Hierarchy Manager.
        
        Args:
            main_chain_name: Name for the Main Chain
        """
        self.main_chain = MainChain(main_chain_name)
        self.sub_chains: Dict[str, SubChain] = {}
        self.system_started_at = time.time()
        self.auto_proof_submission = True
        self.proof_submission_interval = 60.0  # Default 60 seconds
        self.system_stats = {
            "total_operations": 0,
            "total_proofs": 0,
            "system_uptime": 0
        }
    
    def create_sub_chain(self, name: str, domain_type: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create and register a new Sub-Chain.
        
        Args:
            name: Name for the Sub-Chain
            domain_type: Domain type the Sub-Chain will handle
            metadata: Additional metadata for the Sub-Chain
            
        Returns:
            True if Sub-Chain was created successfully, False otherwise
        """
        if name in self.sub_chains:
            return False
        
        # Create Domain-specific Sub-Chain with full functionality
        from domains.generic.chains.domain_chain import DomainChain
        sub_chain = DomainChain(name, domain_type)
        
        # Connect to Main Chain
        connection_metadata = {
            "domain_type": domain_type,
            "created_by": "hierarchy_manager",
            "created_at": time.time(),
            **(metadata or {})
        }
        
        if sub_chain.connect_to_main_chain(self.main_chain):
            self.sub_chains[name] = sub_chain
            
            # Configure automatic proof submission
            if self.auto_proof_submission:
                sub_chain.proof_submission_interval = self.proof_submission_interval
            
            return True
        
        return False
    
    def get_sub_chain(self, name: str) -> Optional[SubChain]:
        """
        Get a Sub-Chain by name.
        
        Args:
            name: Name of the Sub-Chain
            
        Returns:
            Sub-Chain instance or None if not found
        """
        return self.sub_chains.get(name)
    
    def remove_sub_chain(self, name: str) -> bool:
        """
        Remove a Sub-Chain from the hierarchy.
        
        Args:
            name: Name of the Sub-Chain to remove
            
        Returns:
            True if Sub-Chain was removed successfully, False otherwise
        """
        if name not in self.sub_chains:
            return False
        
        # Submit final proof before removal
        sub_chain = self.sub_chains[name]
        if sub_chain.pending_events:
            sub_chain.finalize_sub_chain_block()
            sub_chain.submit_proof_to_main(self.main_chain)
        
        # Remove from tracking
        del self.sub_chains[name]
        
        return True
    
    def start_operation(self, sub_chain_name: str, entity_id: str, 
                       operation_type: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start an operation on a specific Sub-Chain.
        
        Args:
            sub_chain_name: Name of the Sub-Chain
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation to start
            details: Additional operation details
            
        Returns:
            True if operation was started successfully, False otherwise
        """
        sub_chain = self.get_sub_chain(sub_chain_name)
        if not sub_chain:
            return False
        
        success = sub_chain.start_operation(entity_id, operation_type, details)
        if success:
            self.system_stats["total_operations"] += 1
        
        return success
    
    def complete_operation(self, sub_chain_name: str, entity_id: str, 
                          operation_type: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Complete an operation on a specific Sub-Chain.
        
        Args:
            sub_chain_name: Name of the Sub-Chain
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation to complete
            result: Operation result data
            
        Returns:
            True if operation was completed successfully, False otherwise
        """
        sub_chain = self.get_sub_chain(sub_chain_name)
        if not sub_chain:
            return False
        
        return sub_chain.complete_operation(entity_id, operation_type, result)
    
    def trace_entity_across_chains(self, entity_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Trace an entity across all Sub-Chains in the hierarchy.
        
        Args:
            entity_id: Entity identifier to trace
            
        Returns:
            Dictionary mapping Sub-Chain names to entity event histories
        """
        entity_trace = {}
        
        for sub_chain_name, sub_chain in self.sub_chains.items():
            entity_events = sub_chain.get_entity_history(entity_id)
            if entity_events:
                entity_trace[sub_chain_name] = entity_events
        
        return entity_trace
    
    def submit_all_proofs(self) -> Dict[str, bool]:
        """
        Submit proofs from all Sub-Chains to Main Chain.
        
        Returns:
            Dictionary mapping Sub-Chain names to submission success status
        """
        submission_results = {}
        
        for sub_chain_name, sub_chain in self.sub_chains.items():
            # Finalize any pending events first
            if sub_chain.pending_events:
                sub_chain.finalize_sub_chain_block()
            
            # Submit proof
            success = sub_chain.submit_proof_to_main(self.main_chain)
            submission_results[sub_chain_name] = success
            
            if success:
                self.system_stats["total_proofs"] += 1
        
        return submission_results
    
    def finalize_main_chain_block(self) -> Optional[Dict[str, Any]]:
        """
        Finalize a block on the Main Chain.
        
        Returns:
            Information about the finalized Main Chain block
        """
        return self.main_chain.finalize_main_chain_block()
    
    def get_system_integrity_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive system integrity report.
        
        Returns:
            Complete integrity report for the hierarchical system
        """
        # Get Main Chain integrity report
        main_chain_report = self.main_chain.get_hierarchical_integrity_report()
        
        # Add Sub-Chain details
        sub_chain_details = {}
        total_sub_chain_blocks = 0
        total_sub_chain_events = 0
        
        for sub_chain_name, sub_chain in self.sub_chains.items():
            stats = sub_chain.get_domain_statistics()
            sub_chain_details[sub_chain_name] = {
                "domain_type": sub_chain.domain_type,
                "blocks": stats["total_blocks"],
                "events": stats["total_events"],
                "entities": stats["unique_entities"],
                "operations": stats["completed_operations"],
                "chain_valid": stats["chain_valid"],
                "main_chain_connected": stats["main_chain_connected"]
            }
            
            total_sub_chain_blocks += stats["total_blocks"]
            total_sub_chain_events += stats["total_events"]
        
        # Calculate system uptime
        self.system_stats["system_uptime"] = time.time() - self.system_started_at
        
        return {
            "system_overview": {
                "main_chain": main_chain_report["main_chain"],
                "total_sub_chains": len(self.sub_chains),
                "total_sub_chain_blocks": total_sub_chain_blocks,
                "total_sub_chain_events": total_sub_chain_events,
                "system_uptime": self.system_stats["system_uptime"],
                "auto_proof_submission": self.auto_proof_submission
            },
            "main_chain_report": main_chain_report,
            "sub_chain_details": sub_chain_details,
            "system_stats": self.system_stats,
            "integrity_status": "healthy" if self._check_system_integrity() else "compromised"
        }
    
    def _check_system_integrity(self) -> bool:
        """
        Check the integrity of the entire hierarchical system.
        
        Returns:
            True if system integrity is good, False otherwise
        """
        # Check Main Chain integrity
        if not self.main_chain.is_chain_valid():
            return False
        
        # Check all Sub-Chain integrity
        for sub_chain in self.sub_chains.values():
            if not sub_chain.is_chain_valid():
                return False
        
        return True
    
    def get_cross_chain_statistics(self) -> Dict[str, Any]:
        """
        Get statistics that span across multiple chains.
        
        Returns:
            Cross-chain statistics
        """
        # Collect all entities across all Sub-Chains
        all_entities = set()
        domain_distribution = {}
        operation_types = {}
        
        for sub_chain_name, sub_chain in self.sub_chains.items():
            stats = sub_chain.get_domain_statistics()
            
            # Count entities per domain
            domain_distribution[sub_chain.domain_type] = domain_distribution.get(
                sub_chain.domain_type, 0) + stats["unique_entities"]
            
            # Aggregate operation types
            for op_type, count in stats["operation_types"].items():
                operation_types[op_type] = operation_types.get(op_type, 0) + count
            
            # Collect entity IDs (approximate - would need actual entity tracking)
            all_entities.add(f"{sub_chain_name}_entities_{stats['unique_entities']}")
        
        return {
            "total_unique_entities": len(all_entities),
            "domain_distribution": domain_distribution,
            "operation_types": operation_types,
            "cross_chain_operations": self.system_stats["total_operations"],
            "total_proofs_submitted": self.system_stats["total_proofs"]
        }
    
    def configure_auto_proof_submission(self, enabled: bool, interval: float = 60.0) -> None:
        """
        Configure automatic proof submission for all Sub-Chains.
        
        Args:
            enabled: Whether to enable automatic proof submission
            interval: Interval in seconds between proof submissions
        """
        self.auto_proof_submission = enabled
        self.proof_submission_interval = interval
        
        # Update all existing Sub-Chains
        for sub_chain in self.sub_chains.values():
            sub_chain.proof_submission_interval = interval
    
    def execute_system_maintenance(self) -> Dict[str, Any]:
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
    
    def validate_cross_chain_consistency(self) -> Dict[str, Any]:
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
    
    def __str__(self) -> str:
        """String representation of the Hierarchy Manager."""
        return f"HierarchyManager(main_chain={self.main_chain.name}, sub_chains={len(self.sub_chains)})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the Hierarchy Manager."""
        return (f"HierarchyManager(main_chain={self.main_chain.name}, "
                f"sub_chains={list(self.sub_chains.keys())}, "
                f"auto_proof={self.auto_proof_submission}, "
                f"uptime={time.time() - self.system_started_at:.2f}s)")