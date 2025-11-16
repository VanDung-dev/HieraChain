"""
Sub-Chain implementation for Hierarchical-Blockchain Framework.

This module implements the Sub-Chain class that handles domain-specific
business operations and submits proofs to the Main Chain, following
framework guidelines for hierarchical blockchain structure.
"""

import time
from typing import Dict, Any, List, Optional, Callable

from hierarchical_blockchain.core.blockchain import Blockchain
from hierarchical_blockchain.core.consensus.proof_of_authority import ProofOfAuthority
from hierarchical_blockchain.core.utils import sanitize_metadata_for_main_chain, create_event


class SubChain(Blockchain):
    """
    Sub-Chain implementation for the hierarchical blockchain framework.
    
    Sub-Chains act as domain experts (like department heads) and:
    - Handle domain-specific business operations
    - Store detailed domain events and data
    - Submit cryptographic proofs to Main Chain
    - Use entity_id as metadata field within events (not as block identifier)
    """
    
    def __init__(self, name: str, domain_type: str = "generic"):
        """
        Initialize a Sub-Chain.
        
        Args:
            name: Name identifier for the Sub-Chain
            domain_type: Type of domain this Sub-Chain handles
        """
        super().__init__(name)
        self.domain_type = domain_type
        self.consensus = ProofOfAuthority(f"{name}_PoA")
        self.main_chain_connection: Optional[Any] = None
        self.proof_submission_interval: float = 60.0  # Submit proofs every 60 seconds
        self.last_proof_submission: float = 0.0
        self.completed_operations: int = 0
        
        # Register Sub-Chain as authority for its own operations
        self.consensus.add_authority(name, {
            "role": "sub_chain_authority",
            "domain_type": domain_type,
            "permissions": ["domain_operations", "event_creation"],
            "created_at": time.time()
        })
    
    def connect_to_main_chain(self, main_chain: Any) -> bool:
        """
        Connect this Sub-Chain to a Main Chain.
        
        Args:
            main_chain: Main Chain instance to connect to
            
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            # Register with Main Chain
            metadata = {
                "domain_type": self.domain_type,
                "sub_chain_name": self.name,
                "connected_at": time.time(),
                "capabilities": ["domain_operations", "proof_submission"]
            }
            
            if main_chain.register_sub_chain(self.name, metadata):
                self.main_chain_connection = main_chain
                
                # Create connection event
                connection_event = {
                    "event": "main_chain_connection",
                    "timestamp": time.time(),
                    "details": {
                        "main_chain_name": main_chain.name,
                        "connected_at": time.time(),
                        "status": "connected"
                    }
                }
                
                self.add_event(connection_event)
                return True
        except (AttributeError, TypeError, ValueError):
            pass
        
        return False
    
    def start_operation(self, entity_id: str, operation_type: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start a domain-specific operation for an entity.
        
        This follows the guidelines pattern where entity_id is used as metadata
        field within events, not as block identifier.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation to start
            details: Additional operation details
            
        Returns:
            True if operation was started successfully, False otherwise
        """
        # Create properly structured event following guidelines
        event = create_event(
            entity_id=entity_id,  # Metadata field, not block identifier
            event_type="operation_start",
            details={
                "operation_type": operation_type,
                "domain_type": self.domain_type,
                "started_by": self.name,
                "operation_details": details or {},
                "started_at": time.time()
            }
        )
        
        self.add_event(event)
        return True
    
    def complete_operation(self, entity_id: str, operation_type: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Complete a domain-specific operation for an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            operation_type: Type of operation being completed
            result: Operation result data
            
        Returns:
            True if operation was completed successfully, False otherwise
        """
        # Create completion event
        event = create_event(
            entity_id=entity_id,  # Metadata field
            event_type="operation_complete",
            details={
                "operation_type": operation_type,
                "domain_type": self.domain_type,
                "completed_by": self.name,
                "result": result or {},
                "completed_at": time.time()
            }
        )
        
        self.add_event(event)
        self.completed_operations += 1
        return True
    
    def update_entity_status(self, entity_id: str, status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update the status of an entity.
        
        Args:
            entity_id: Entity identifier (used as metadata)
            status: New status for the entity
            details: Additional status details
            
        Returns:
            True if status was updated successfully, False otherwise
        """
        event = create_event(
            entity_id=entity_id,  # Metadata field
            event_type="status_update",
            details={
                "new_status": status,
                "domain_type": self.domain_type,
                "updated_by": self.name,
                "status_details": details or {},
                "updated_at": time.time()
            }
        )
        
        self.add_event(event)
        return True
    
    def submit_proof_to_main(self, main_chain: Any, metadata_filter: Optional[Callable] = None) -> bool:
        """
        Submit cryptographic proof to Main Chain.
        
        This follows the guidelines pattern for proof submission where
        Sub-Chains submit proofs with summary metadata, not detailed data.
        
        Args:
            main_chain: Main Chain to submit proof to
            metadata_filter: Optional function to generate custom metadata
            
        Returns:
            True if proof was submitted successfully, False otherwise
        """
        if not self.chain or len(self.chain) <= 1:  # Only genesis block
            return False
        
        # Get latest block for proof
        latest_block = self.get_latest_block()
        
        # Generate summary metadata (not detailed domain data)
        if metadata_filter:
            metadata = metadata_filter(self)
        else:
            metadata = self._generate_default_proof_metadata()
        
        # Submit proof to Main Chain
        success = main_chain.add_proof(
            sub_chain_name=self.name,
            proof_hash=latest_block.hash,
            metadata=metadata
        )
        
        if success:
            self.last_proof_submission = time.time()
            
            # Create proof submission event in Sub-Chain
            proof_event = {
                "event": "proof_submitted",
                "timestamp": time.time(),
                "details": {
                    "main_chain_name": main_chain.name,
                    "proof_hash": latest_block.hash,
                    "block_index": latest_block.index,
                    "submitted_at": time.time()
                }
            }
            
            self.add_event(proof_event)
        
        return success
    
    def _generate_default_proof_metadata(self) -> Dict[str, Any]:
        """
        Generate default proof metadata for Main Chain submission.
        
        This creates summary metadata only, no detailed domain data.
        
        Returns:
            Summary metadata suitable for Main Chain
        """
        latest_block = self.get_latest_block()
        
        # Count different event types in recent blocks
        recent_events = []
        for block in self.chain[-5:]:  # Last 5 blocks
            recent_events.extend(block.events)
        
        event_counts = {}
        entity_count = set()
        
        for event in recent_events:
            event_type = event.get("event", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            if "entity_id" in event:
                entity_count.add(event["entity_id"])
        
        # Create summary metadata (following guidelines)
        metadata = {
            "domain_type": self.domain_type,
            "latest_block_index": latest_block.index,
            "total_blocks": len(self.chain),
            "recent_events": len(recent_events),
            "unique_entities": len(entity_count),
            "completed_operations": self.completed_operations,
            "event_types": list(event_counts.keys()),
            "proof_timestamp": time.time()
        }
        
        return sanitize_metadata_for_main_chain(metadata)
    
    def should_submit_proof(self) -> bool:
        """
        Check if it's time to submit a proof to Main Chain.
        
        Returns:
            True if proof should be submitted, False otherwise
        """
        current_time = time.time()
        time_since_last = current_time - self.last_proof_submission
        
        return (time_since_last >= self.proof_submission_interval and 
                len(self.pending_events) > 0)
    
    def auto_submit_proof_if_needed(self) -> bool:
        """
        Automatically submit proof if conditions are met.
        
        Returns:
            True if proof was submitted, False otherwise
        """
        if self.should_submit_proof() and self.main_chain_connection:
            return self.submit_proof_to_main(self.main_chain_connection)
        return False
    
    def get_entity_history(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get complete history of events for a specific entity.
        
        Args:
            entity_id: Entity identifier to search for
            
        Returns:
            List of events for the specified entity, ordered by timestamp
        """
        entity_events = self.get_events_by_entity(entity_id)
        
        # Sort by timestamp
        entity_events.sort(key=lambda x: x.get("timestamp", 0))
        
        return entity_events
    
    def get_domain_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about this Sub-Chain's domain operations.
        
        Returns:
            Dictionary containing domain statistics
        """
        base_stats = self.get_chain_stats()
        
        # Count entities and operations
        all_events = []
        for block in self.chain:
            all_events.extend(block.events)
        
        unique_entities = set()
        operation_types = {}
        
        for event in all_events:
            if "entity_id" in event:
                unique_entities.add(event["entity_id"])
            
            event_type = event.get("event", "unknown")
            operation_types[event_type] = operation_types.get(event_type, 0) + 1
        
        return {
            **base_stats,
            "domain_type": self.domain_type,
            "unique_entities": len(unique_entities),
            "completed_operations": self.completed_operations,
            "operation_types": operation_types,
            "main_chain_connected": self.main_chain_connection is not None,
            "last_proof_submission": self.last_proof_submission,
            "proof_submission_interval": self.proof_submission_interval
        }
    
    def finalize_sub_chain_block(self) -> Optional[Dict[str, Any]]:
        """
        Finalize a block on the Sub-Chain using PoA consensus.
        
        Returns:
            Information about the finalized block, or None if no pending events
        """
        if not self.pending_events:
            return None
        
        # Create block with pending events
        new_block = self.create_block()
        
        # Finalize block using PoA consensus
        finalized_block = self.consensus.finalize_block(new_block, self.name)
        
        # Add finalized block to chain
        if self.add_block(finalized_block):
            # Auto-submit proof if needed
            self.auto_submit_proof_if_needed()
            
            return {
                "block_index": finalized_block.index,
                "block_hash": finalized_block.hash,
                "events_count": len(finalized_block.events),
                "finalized_at": time.time(),
                "domain_type": self.domain_type
            }
        
        return None
    
    def __str__(self) -> str:
        """String representation of the Sub-Chain."""
        return f"SubChain(name={self.name}, domain={self.domain_type}, blocks={len(self.chain)}, operations={self.completed_operations})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the Sub-Chain."""
        return (f"SubChain(name={self.name}, domain_type={self.domain_type}, "
                f"blocks={len(self.chain)}, operations={self.completed_operations}, "
                f"main_chain_connected={self.main_chain_connection is not None})")