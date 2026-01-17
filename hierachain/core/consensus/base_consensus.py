"""
Base Consensus mechanism for HieraChain Framework.

This module defines the abstract base class for consensus mechanisms.
The framework supports various consensus algorithms while maintaining
the event-based model and hierarchical structure principles.
"""

import logging
import pyarrow as pa
from abc import ABC, abstractmethod
from typing import Any

from hierachain.core.block import Block
from hierachain.config.settings import settings
from hierachain.security.verify.zk_verifier import get_zk_verifier

logger = logging.getLogger(__name__)


class BaseConsensus(ABC):
    """
    Abstract base class for consensus mechanisms.
    
    This class defines the interface that all consensus mechanisms must implement
    in the HieraChain framework. It ensures that consensus algorithms
    work with the event-based model and support the hierarchical structure.
    """
    
    def __init__(self, name: str):
        """
        Initialize the consensus mechanism.
        
        Args:
            name: Name of the consensus mechanism
        """
        self.name = name
        self.config: dict[str, Any] = {}

    def get_validator_count(self) -> int:
        """
        Get the number of active validators/authorities.
        
        Returns:
            The count of entities capable of signing blocks.
        """
        return 0
    
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
        raise NotImplementedError("Subclasses must implement validate_block()")
    
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
        raise NotImplementedError("Subclasses must implement finalize_block()")
    
    @abstractmethod
    def can_create_block(self, authority_id: str | None = None) -> bool:
        """
        Check if a block can be created by the given authority.
        
        Args:
            authority_id: ID of the authority requesting block creation
            
        Returns:
            True if block creation is allowed, False otherwise
        """
        raise NotImplementedError("Subclasses must implement can_create_block()")
    
    def validate_event_for_consensus(self, event: dict[str, Any]) -> bool:
        """
        Validate an event according to consensus-specific rules.
        
        This method can be overridden by specific consensus implementations
        to add additional validation rules for events.
        
        Args:
            event: Event to validate
            
        Returns:
            True if event is valid for this consensus, False otherwise
        """
        # Check if input is a PyArrow object
        if isinstance(event, (pa.Table, pa.RecordBatch)):
            return True

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
        if "details" in event:
            details = event["details"]
            if isinstance(details, dict):
                # Check only non-hash/signature fields
                for key, value in details.items():
                    if key not in ["authority_signature", "signature", "hash", "proof_hash"]:
                        value_str = str(value).lower()
                        for term in forbidden_terms:
                            if term in value_str:
                                return False
            elif isinstance(details, str):
                # details might be a JSON string as per Arrow schema
                details_lower = details.lower()
                for term in forbidden_terms:
                    if term in details_lower:
                        return False

        # Check other top-level fields (excluding hash/signature fields)
        for key, value in event.items():
            if key not in ["authority_signature", "signature", "hash", "proof_hash", "details", "event", "timestamp"]:
                value_str = str(value).lower()
                for term in forbidden_terms:
                    if term in value_str:
                        return False
        
        return True
    
    def get_consensus_info(self) -> dict[str, Any]:
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
    
    def update_config(self, config: dict[str, Any]) -> None:
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
    
    @staticmethod
    def _verify_block_zk_proof(block: Block, previous_block: Block | None = None) -> bool:
        """
        Verify ZK proof attached to a block's consensus event.

        This is a shared implementation that child classes can use directly
        or override if they need custom logic.

        Args:
            block: Block to verify
            previous_block: Previous block for state root (optional)

        Returns:
            True if ZK proof is valid or not required, False otherwise
        """
        if not settings.ENABLE_ZK_PROOFS:
            return True

        events = block.to_event_list() if hasattr(block, 'to_event_list') else []

        zk_proof = None
        details: dict[str, Any] = {}

        for event in events:
            if event.get("event") == "consensus_finalization":
                details = event.get("details", {})
                if "zk_proof" in details:
                    zk_proof = details["zk_proof"]
                    break

        # If no ZK proof and not required, accept
        if zk_proof is None:
            if settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN:
                logger.warning(f"Block {block.index}: ZK proof required but missing")
                return False
            return True

        # Build public inputs and verify
        try:
            # Use singleton verifier
            verifier = get_zk_verifier()

            # Determine old_state_root from details or previous_block
            old_state = details.get("previous_state")
            if old_state is None and previous_block:
                old_state = getattr(previous_block, 'merkle_root', None) or "genesis"

            public_inputs = {
                "old_state_root": old_state or "",
                "new_state_root": (
                    details.get("current_state")
                    or getattr(block, 'merkle_root', None)
                    or block.hash
                ),
                "block_index": block.index
            }

            # Convert hex string to bytes if needed
            if isinstance(zk_proof, str):
                zk_proof = bytes.fromhex(zk_proof)

            return verifier.verify(zk_proof, public_inputs)

        except Exception as e:
            logger.error(f"ZK verification error in block {block.index}: {e}")
            return False

    def __str__(self) -> str:
        """String representation of the consensus mechanism."""
        return f"{self.__class__.__name__}(name={self.name})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the consensus mechanism."""
        return f"{self.__class__.__name__}(name={self.name}, config={self.config})"