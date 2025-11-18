"""
Base Consensus mechanism for Hierarchical-Blockchain Framework.

This module defines the abstract base class for consensus mechanisms.
The framework supports various consensus algorithms while maintaining
the event-based model and hierarchical structure principles.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from hierarchical_blockchain.core.block import Block


class BaseConsensus(ABC):
    """
    Abstract base class for consensus mechanisms.
    
    This class defines the interface that all consensus mechanisms must implement
    in the hierarchical blockchain framework. It ensures that consensus algorithms
    work with the event-based model and support the hierarchical structure.
    """
    
    def __init__(self, name: str):
        """
        Initialize the consensus mechanism.
        
        Args:
            name: Name of the consensus mechanism
        """
        self.name = name
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    def validate_block(self, block: Block, previous_block: Block) -> bool:
        """
        Validate a block according to the consensus rules.
        
        Args:
            block: Block to validate
            previous_block: Previous block in the chain
            
        Returns:
            True if block is valid according to consensus rules, False otherwise
        """
        pass
    
    @abstractmethod
    def finalize_block(self, block: Block) -> Block:
        """
        Finalize a block according to the consensus mechanism.
        
        This method applies consensus-specific modifications to the block
        (e.g., proof-of-work nonce, authority signatures, etc.)
        
        Args:
            block: Block to finalize
            
        Returns:
            Finalized block
        """
        pass
    
    @abstractmethod
    def can_create_block(self, authority_id: Optional[str] = None) -> bool:
        """
        Check if a block can be created by the given authority.
        
        Args:
            authority_id: ID of the authority requesting block creation
            
        Returns:
            True if block creation is allowed, False otherwise
        """
        pass
    
    def validate_event_for_consensus(self, event: Dict[str, Any]) -> bool:
        """
        Validate an event according to consensus-specific rules.
        
        This method can be overridden by specific consensus implementations
        to add additional validation rules for events.
        
        Args:
            event: Event to validate
            
        Returns:
            True if event is valid for this consensus, False otherwise
        """
        # Basic validation - ensure it's an event, not a transaction
        if not isinstance(event, dict):
            return False
        
        # Must have event type (not transaction type)
        if "event" not in event:
            return False
        
        # Must have timestamp
        if "timestamp" not in event:
            return False
        
        # Should not contain cryptocurrency terms
        # Check only in relevant fields, not in hash/signature fields
        forbidden_terms = ["transaction", "mining", "coin", "token", "wallet", "fee"]
        
        # Check event type field
        event_type = str(event.get("event", "")).lower()
        for term in forbidden_terms:
            if term in event_type:
                return False
        
        # Check details field (but exclude hash/signature fields)
        if "details" in event and isinstance(event["details"], dict):
            details = event["details"]
            # Check only non-hash/signature fields
            for key, value in details.items():
                if key not in ["authority_signature", "signature", "hash", "proof_hash"]:
                    value_str = str(value).lower()
                    for term in forbidden_terms:
                        if term in value_str:
                            return False
        
        # Check other top-level fields (excluding hash/signature fields)
        for key, value in event.items():
            if key not in ["authority_signature", "signature", "hash", "proof_hash", "details", "event", "timestamp"]:
                value_str = str(value).lower()
                for term in forbidden_terms:
                    if term in value_str:
                        return False
        
        return True
    
    def get_consensus_info(self) -> Dict[str, Any]:
        """
        Get information about the consensus mechanism.
        
        Returns:
            Dictionary containing consensus information
        """
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "config": self.config
        }
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update consensus configuration.
        
        Args:
            config: New configuration parameters
        """
        self.config.update(config)
    
    def reset_consensus_state(self) -> None:
        """
        Reset any internal consensus state.
        
        This method can be overridden by specific consensus implementations
        to reset their internal state when needed.
        """
        pass
    
    def get_block_creation_difficulty(self) -> float:
        """
        Get the current difficulty for block creation.
        
        Returns:
            Difficulty value (interpretation depends on consensus mechanism)
        """
        return 1.0  # Default difficulty
    
    def estimate_block_time(self) -> float:
        """
        Estimate the time required to create a new block.
        
        Returns:
            Estimated time in seconds
        """
        return 10.0  # Default 10 seconds
    
    def __str__(self) -> str:
        """String representation of the consensus mechanism."""
        return f"{self.__class__.__name__}(name={self.name})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the consensus mechanism."""
        return f"{self.__class__.__name__}(name={self.name}, config={self.config})"