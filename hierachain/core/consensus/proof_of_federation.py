"""
Proof of Federation (PoF) consensus mechanism.

This module implements a Federated consensus mechanism designed for 
consortium blockchains (e.g., Healthcare, Education, Supply Chain Consortia).
It replaces the static authority model with a rotating leader schedule,
ensuring fair participation and removing single points of failure.
"""

import time
import hashlib
from typing import Dict, Any, List, Optional

from hierachain.core.consensus.base_consensus import BaseConsensus
from hierachain.core.block import Block


class ProofOfFederation(BaseConsensus):
    """
    Proof of Federation (PoF) Consensus.
    
    A Round-Robin based consensus mechanism suitable for semi-trusted consortiums.
    
    Key Features:
    - Rotating Leader: Authorities take turns creating blocks based on block height.
    - Deterministic Schedule: Leader = (BlockHeight) % (TotalAuthorities).
    - Fault Tolerance: If a leader misses their turn, the protocol can skip to the next
    (implementation handled via timeout/view-change logic in higher layers).
    """

    def __init__(self, name: str = "ProofOfFederation"):
        """
        Initialize Proof of Federation.
        
        Args:
            name: Name of the consensus instance.
        """
        super().__init__(name)
        
        # Internal state
        self.validators: List[str] = []  # Ordered list of validator IDs
        self.validator_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Configuration defaults (can be updated via settings)
        self.config = {
            "block_interval": 5.0,  # Faster than PoA (typically 10s)
            "min_validators": 3,    # Minimum size for a valid federation
            "enforce_rotation": True
        }

    def add_validator(self, validator_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a validator to the federation.
        
        Args:
            validator_id: Unique identifier for the validator node.
            metadata: Info about the organization (e.g., "Hospital A", "University B").
            
        Returns:
            True if added, False if already exists.
        """
        if validator_id in self.validators:
            return False
            
        self.validators.append(validator_id)
        # Keep list sorted to ensure deterministic order across all nodes
        self.validators.sort()
        
        self.validator_metadata[validator_id] = metadata or {}
        return True

    def remove_validator(self, validator_id: str) -> bool:
        """
        Remove a validator from the federation.
        
        Args:
            validator_id: ID to remove.
            
        Returns:
            True if removed, False if not found.
        """
        if validator_id in self.validators:
            self.validators.remove(validator_id)
            self.validator_metadata.pop(validator_id, None)
            return True
        return False

    def get_current_leader(self, block_index: int) -> Optional[str]:
        """
        Determine the expected leader for a specific block index.
        
        Algorithm: Leader = Validators[ BlockIndex % ValidatorCount ]
        
        Args:
            block_index: The height/index of the block to be created.
            
        Returns:
            The validator_id of the expected leader, or None if no validators.
        """
        if not self.validators:
            return None
            
        leader_idx = block_index % len(self.validators)
        return self.validators[leader_idx]

    def can_create_block(self, authority_id: Optional[str] = None) -> bool:
        """
        Check if the authority can create a block.
        
        Args:
            authority_id: The ID of the authority attempting to create a block.
            
        Returns:
            True if the authority can create a block, False otherwise.
        """
        # 1. Check if we have enough validators
        min_validators = self.config.get("min_validators", 3)
        if len(self.validators) < min_validators:
            return False

        # 2. If authority_id provided, check if it's a valid validator
        if authority_id and authority_id not in self.validators:
            return False
            
        return True

    def validate_block_proposer(self, block_index: int, proposer_id: str) -> bool:
        """
        Strictly validate if the proposer is the correct leader for this block height.
        
        Args:
            block_index: Index of the block.
            proposer_id: ID of the node that signed/proposed the block.
            
        Returns:
            True if it is this proposer's turn.
        """
        expected_leader = self.get_current_leader(block_index)
        return expected_leader == proposer_id

    def validate_block(self, block: Block, previous_block: Block) -> bool:
        """
        Validate a block according to PoF rules.
        
        1. Basic structure check.
        2. Time interval check.
        3. **Leader Rotation Check**: Verify the block signer was the correct leader for this height.
        """
        # 1. Basic structure
        if not block.validate_structure():
            return False
            
        # 2. Timing check
        time_diff = block.timestamp - previous_block.timestamp
        # Allow slight leniency (drifting clocks), e.g., 80% of interval
        if time_diff < self.config["block_interval"] * 0.8:
            return False

        # 3. Leader Check
        # We look for the consensus signature event to find who signed it
        signer_id = self._extract_signer_id(block)
        
        if not signer_id:
            # Block must be signed in PoF
            return False
            
        if self.config["enforce_rotation"]:
            if not self.validate_block_proposer(block.index, signer_id):
                # "It wasn't your turn!"
                return False
                
        return True

    def finalize_block(self, block: Block, authority_id: Optional[str] = None) -> Block:
        """
        Finalize block by attaching the Federation Signature.
        """
        if not authority_id or not self.can_create_block(authority_id):
            # In a real implementation we might raise an error, but here we return unmodified
            # or let it fail validation later.
            return block

        # Create signature payload
        signature_data = f"{block.hash}:{authority_id}:{block.index}:{time.time()}"
        signature = hashlib.sha256(signature_data.encode()).hexdigest()

        consensus_metadata = {
            "consensus_type": "proof_of_federation",
            "leader_id": authority_id,
            "signature": signature,
            "validators_count": len(self.validators),
            "round": block.index,
            "finalized_at": time.time()
        }
        
        # Append consensus event
        # Note: In Arrow-based blocks, this appends to the internal list/table
        events = block.to_event_list()
        events.append({
            "event": "consensus_finalization",
            "timestamp": time.time(),
            "details": consensus_metadata
        })
        
        # Return new block object
        return Block(
            index=block.index,
            previous_hash=block.previous_hash,
            timestamp=block.timestamp,
            events=events,
            nonce=block.nonce
        )

    @staticmethod
    def _extract_signer_id(block: Block) -> Optional[str]:
        """Helper to find the signer ID from the block's events."""
        events = block.to_event_list()
        for event in reversed(events): # Check end of block first
            if event.get("event") == "consensus_finalization":
                return event.get("details", {}).get("leader_id")
        return None

    def get_consensus_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": "ProofOfFederation",
            "validator_count": len(self.validators),
            "validators": self.validators,
            "config": self.config
        }

    def estimate_block_time(self) -> float:
        return self.config["block_interval"]
