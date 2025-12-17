"""
Proof of Authority consensus mechanism for HieraChain Framework.

This module implements a Proof of Authority (PoA) consensus mechanism suitable
for the HieraChain framework where specific authorities (Main Chain,
Sub-Chains) have designated roles and permissions for block creation.
"""

import time
import hashlib
from typing import Any, Optional

from hierachain.core.consensus.base_consensus import BaseConsensus
from hierachain.core.block import Block


class ProofOfAuthority(BaseConsensus):
    """
    Proof of Authority consensus mechanism.
    
    This consensus mechanism is ideal for the HieraChain framework
    where:
    - Main Chain acts as the root authority
    - Sub-Chains are authorized domain-specific authorities
    - Block creation is controlled by authorized entities
    - No energy-intensive mining (suitable for business applications)
    """
    
    def __init__(self, name: str = "ProofOfAuthority"):
        """
        Initialize Proof of Authority consensus.
        
        Args:
            name: Name of the consensus mechanism
        """
        super().__init__(name)
        self.authorities: set[str] = set()
        self.authority_metadata: dict[str, dict[str, Any]] = {}
        self.block_interval: float = 10.0  # Default 10 seconds between blocks
        self.config = {
            "block_interval": self.block_interval,
            "require_authority_signature": True,
            "max_authorities": 100
        }

    def add_authority(self, authority_id: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Add a new authority to the consensus mechanism.
        
        Args:
            authority_id: Unique identifier for the authority
            metadata: Additional metadata about the authority
            
        Returns:
            True if authority was added successfully, False otherwise
        """
        if len(self.authorities) >= self.config["max_authorities"]:
            return False
        
        self.authorities.add(authority_id)
        self.authority_metadata[authority_id] = metadata or {}
        return True
    
    def remove_authority(self, authority_id: str) -> bool:
        """
        Remove an authority from the consensus mechanism.
        
        Args:
            authority_id: Authority identifier to remove
            
        Returns:
            True if authority was removed successfully, False otherwise
        """
        if authority_id in self.authorities:
            self.authorities.remove(authority_id)
            self.authority_metadata.pop(authority_id, None)
            return True
        return False
    
    def is_authority(self, authority_id: str) -> bool:
        """
        Check if an entity is an authorized authority.
        
        Args:
            authority_id: Authority identifier to check
            
        Returns:
            True if entity is an authority, False otherwise
        """
        return authority_id in self.authorities

    def can_create_block(self, authority_id: str | None = None) -> bool:
        """
        Check if a block can be created by the given authority.
        
        Args:
            authority_id: ID of the authority requesting block creation
            
        Returns:
            True if block creation is allowed, False otherwise
        """
        if authority_id is None:
            return False
        
        return self.is_authority(authority_id)
    
    def validate_block(self, block: Block, previous_block: Block) -> bool:
        """
        Validate a block according to PoA consensus rules.
        
        Args:
            block: Block to validate
            previous_block: Previous block in the chain
            
        Returns:
            True if block is valid according to PoA rules, False otherwise
        """
        # Basic block structure validation
        if not block.validate_structure():
            return False
        
        # Check block timing (not too fast)
        time_diff = block.timestamp - previous_block.timestamp
        if time_diff < self.config["block_interval"] / 2:
            return False

        events = block.to_event_list()
        for event in events:
            if not self.validate_event_for_consensus(event):
                return False
        
        # Check if block contains authority signature (if required)
        if self.config["require_authority_signature"]:
            if not self._has_valid_authority_signature(block):
                return False
        
        return True
    
    def finalize_block(self, block: Block, authority_id: Optional[str] = None) -> Block:
        """
        Finalize a block according to PoA consensus.
        
        Args:
            block: Block to finalize
            authority_id: ID of the authority finalizing the block
            
        Returns:
            Finalized block with PoA consensus data
        """
        if authority_id and self.is_authority(authority_id):
            # Add authority signature to the block
            authority_signature = self._create_authority_signature(block, authority_id)
            
            # Add consensus metadata to the first event or create a consensus event
            consensus_event = {
                "event": "consensus_finalization",
                "entity_id": "system_consensus",
                "timestamp": time.time(),
                "details": {
                    "consensus_type": "proof_of_authority",
                    "authority_id": authority_id,
                    "authority_signature": authority_signature,
                    "finalized_at": time.time()
                }
            }
            
            # Add consensus event to the block
            current_events = block.to_event_list()
            current_events.append(consensus_event)
            
            # Create new block preserving other properties
            block = Block(
                index=block.index,
                events=current_events,
                previous_hash=block.previous_hash,
                timestamp=block.timestamp,
                nonce=block.nonce
            )
        
        return block
    
    @staticmethod
    def _create_authority_signature(block: Block, authority_id: str) -> str:
        """
        Create an authority signature for the block.
        
        Args:
            block: Block to sign
            authority_id: Authority creating the signature
            
        Returns:
            Authority signature string
        """
        signature_data = {
            "block_hash": block.hash,
            "authority_id": authority_id,
            "timestamp": time.time(),
            "block_index": block.index
        }

        # Create a simple signature (in production, use proper cryptographic signatures)
        sig_str = (f"{signature_data['block_hash']}{authority_id}{signature_data['timestamp']}")
        return hashlib.sha256(sig_str.encode()).hexdigest()

    def _has_valid_authority_signature(self, block: Block) -> bool:
        """
        Check if block has a valid authority signature.
        
        Args:
            block: Block to check
            
        Returns:
            True if block has valid authority signature, False otherwise
        """
        # Look for consensus finalization event
        # Handle Arrow Table events gracefully
        events = block.to_event_list()
        for event in events:
            if (event.get("event") == "consensus_finalization" and
                "details" in event and
                "authority_id" in event.get("details", {}) and
                "authority_signature" in event.get("details", {})):

                authority_id = event["details"]["authority_id"]
                if self.is_authority(authority_id):
                    return True
        
        return False

    def get_next_authority(self, current_block_index: int) -> str | None:
        """
        Get the next authority that should create a block (round-robin).
        
        Args:
            current_block_index: Current block index
            
        Returns:
            Authority ID that should create the next block, or None if no authorities
        """
        if not self.authorities:
            return None
        
        authorities_list = sorted(list(self.authorities))
        next_index = (current_block_index + 1) % len(authorities_list)
        return authorities_list[next_index]

    def get_authority_stats(self) -> dict[str, Any]:
        """
        Get statistics about authorities.
        
        Returns:
            Dictionary containing authority statistics
        """
        return {
            "total_authorities": len(self.authorities),
            "authorities": list(self.authorities),
            "authority_metadata": self.authority_metadata,
            "max_authorities": self.config["max_authorities"]
        }

    def validate_event_for_consensus(self, event: dict[str, Any]) -> bool:
        """
        Validate an event according to PoA consensus rules.
        
        Args:
            event: Event to validate
            
        Returns:
            True if event is valid for PoA consensus, False otherwise
        """
        # Use base validation first
        if not super().validate_event_for_consensus(event):
            return False
        
        # Additional PoA-specific validation
        # Ensure event has proper structure for business applications
        if event.get("entity_id") is not None:
            # entity_id should be used as metadata, not as identifier
            if not isinstance(event["entity_id"], str):
                return False
        

        event_type = event.get("event", "")
        # Allow custom event types but reject cryptocurrency-related ones
        crypto_event_types = ["transaction", "mining", "coin_transfer", "wallet_update"]
        if event_type in crypto_event_types:
            return False
        
        return True
    
    def reset_consensus_state(self) -> None:
        """Reset PoA consensus state."""
        # Keep authorities but reset any temporary state
        pass
    
    def get_block_creation_difficulty(self) -> float:
        """
        Get block creation difficulty for PoA (always 1.0 since no mining).
        
        Returns:
            Difficulty value (1.0 for PoA)
        """
        return 1.0
    
    def estimate_block_time(self) -> float:
        """
        Estimate block creation time for PoA.
        
        Returns:
            Estimated time in seconds
        """
        return self.config["block_interval"]
    
    def __str__(self) -> str:
        """String representation of PoA consensus."""
        return f"ProofOfAuthority(authorities={len(self.authorities)})"
    
    def __repr__(self) -> str:
        """Detailed string representation of PoA consensus."""
        return (f"ProofOfAuthority(name={self.name}, "
                f"authorities={len(self.authorities)}, "
                f"block_interval={self.config['block_interval']})")
