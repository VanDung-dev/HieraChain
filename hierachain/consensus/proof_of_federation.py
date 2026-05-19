"""
Proof of Federation (PoF) consensus mechanism.

This module implements a Federated consensus mechanism designed for consortium
blockchains (e.g., Healthcare, Education, Supply Chain Consortia).
It replaces the static authority model with a rotating leader schedule,
ensuring fair participation and removing single points of failure.

Enhanced with ZK Proof verification for trustless block validation.
"""

import time
from typing import Any

from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

from hierachain.consensus.base_consensus import (
    BaseConsensus, _verify_block_zk_proof
)
from hierachain.core.block import Block
from hierachain.security.security_utils import verify_signature
from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()


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

    def __init__(self, name: str = "ProofOfFederation",
                 signing_key_hex: str | None = None):
        """
        Initialize Proof of Federation.
    
        Args:
            name: Name of the consensus instance.
            signing_key_hex: Optional hex-encoded Ed25519 signing key for
                             creating federation signatures. If omitted,
                             signing operations will log a warning.
        """
        super().__init__(name)
    
        # Internal state
        self.validators: list[str] = []  # Ordered list of validator IDs
        self.validator_metadata: dict[str, dict[str, Any]] = {}
        self._signing_key: SigningKey | None = None
        if signing_key_hex:
            try:
                key_bytes = HexEncoder.decode(signing_key_hex.encode("utf-8"))
                self._signing_key = SigningKey(key_bytes)
            except Exception as e:
                logger.error("Invalid signing_key_hex for PoF: %s", e)
    
        # Configuration defaults (can be updated via settings)
        self.config = {
            "block_interval": 5.0,  # Faster than PoA (typically 10s)
            "min_validators": 3,    # Minimum size for a valid federation
            "enforce_rotation": True
        }

    def get_validator_count(self) -> int:
        """Get the number of active validators."""
        return len(self.validators)

    def add_validator(
        self, validator_id: str, metadata: dict[str, Any] | None = None
    ) -> bool:
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

    def add_authority(
        self, authority_id: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """Alias for add_validator for compatibility."""
        return self.add_validator(authority_id, metadata)

    def remove_authority(self, authority_id: str) -> bool:
        """Alias for remove_validator for compatibility."""
        return self.remove_validator(authority_id)

    def is_authority(self, authority_id: str) -> bool:
        """Check if an ID is an active authority/validator."""
        return authority_id in self.validators

    def get_current_leader(self, block_index: int) -> str | None:
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

    def can_create_block(self, authority_id: str | None = None) -> bool:
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

        Args:
            block: Block to validate.
            previous_block: Previous block in the chain.

        Returns:
            True if block is valid according to PoF rules, False otherwise
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
        signer_id = _extract_signer_id(block)

        if not signer_id:
            return False

        if (self.config["enforce_rotation"] and
                not self.validate_block_proposer(block.index, signer_id)):
            return False

        # 4. Federation signature verification
        if not _verify_block_quorum(block, self.validator_metadata):
            logger.error("Block %d federation signature verification FAILED", block.index)
            return False

        # 5. ZK Proof Verification (if enabled)
        # Uses shared implementation from BaseConsensus
        zk_valid = _verify_block_zk_proof(block, previous_block)
        if not zk_valid:
            logger.error("Block %d ZK proof verification FAILED", block.index)
            return False
        logger.debug("Block %d ZK proof verified", block.index)

        return True

    def finalize_block(self, block: Block, authority_id: str | None = None) -> Block:
        """Finalize block by attaching the Federation Signature."""
        if not authority_id or not self.can_create_block(authority_id):
            return block

        signature = _create_federation_signature(block, self._signing_key)
        consensus_metadata = {
            "consensus_type": "proof_of_federation",
            "leader_id": authority_id,
            "signature": signature,
            "validators_count": len(self.validators),
            "round": block.index,
            "finalized_at": time.time()
        }

        events = block.to_event_list()
        events.append({
            "event": "consensus_finalization",
            "timestamp": time.time(),
            "details": consensus_metadata
        })

        return Block(
            index=block.index,
            previous_hash=block.previous_hash,
            timestamp=block.timestamp,
            events=events,
            nonce=block.nonce
        )

    def get_consensus_info(self) -> dict[str, Any]:
        """Get information about the current consensus state."""
        return {
            "name": self.name,
            "type": "ProofOfFederation",
            "validator_count": len(self.validators),
            "validators": self.validators,
            "config": self.config
        }

    def estimate_block_time(self) -> float:
        return self.config["block_interval"]

    def verify_quorum_signatures(
        self,
        message: bytes,
        signatures: list[dict[str, str]],
        required_count: int | None = None
    ) -> bool:
        """Verify that a message is signed by a quorum of validators."""
        if not self.validators:
            return False

        required_count = _get_required_quorum_count(
            len(self.validators), required_count
        )
        if len(signatures) < required_count:
            return False

        valid_count = 0
        seen_validators: set[str] = set()

        for sig_entry in signatures:
            validator_id = sig_entry.get("validator_id")
            if _is_signature_valid(
                sig_entry, message, self.validators,
                self.validator_metadata, seen_validators
            ):
                valid_count += 1
                seen_validators.add(validator_id or "")

            if valid_count >= required_count:
                return True

        return False


def _extract_signer_id(block: Block) -> str | None:
    """Helper to find the signer ID from the block's events."""
    events = block.to_event_list()
    # Check end of block first for performance
    for event in reversed(events):
        if event.get("event") == "consensus_finalization":
            return event.get("details", {}).get("leader_id")
    return None


def _create_federation_signature(block: Block, signing_key: SigningKey | None) -> str:
    """Create an Ed25519 federation signature for the block.

    Signs the block hash with the leader's Ed25519 signing key.

    Args:
        block: Block to sign.
        signing_key: Ed25519 signing key of the leader.

    Returns:
        Hex-encoded Ed25519 signature, or empty string if no signing key.
    """
    if signing_key is None:
        logger.warning("No signing key configured for PoF — cannot sign block %d", block.index)
        return ""
    message = block.hash.encode("utf-8")
    signed = signing_key.sign(message)
    return signed.signature.hex()


def _get_required_quorum_count(
    total_validators: int, manually_required: int | None
) -> int:
    """Calculate the required number of signatures for a quorum."""
    if manually_required is not None:
        return manually_required
    # Default BFT-style quorum: 2/3 + 1
    return (total_validators * 2) // 3 + 1


def _is_signature_valid(
    sig_entry: dict[str, str],
    message: bytes,
    validators: list[str],
    validator_metadata: dict[str, Any],
    seen_validators: set[str]
) -> bool:
    """Validate a single signature from the signatures list."""
    validator_id = sig_entry.get("validator_id")
    signature = sig_entry.get("signature")

    if not validator_id or not signature:
        return False

    if validator_id not in validators or validator_id in seen_validators:
        return False

    public_key = validator_metadata.get(validator_id, {}).get("public_key")
    if not public_key:
        return False

    from hierachain.security.security_utils import verify_signature
    return verify_signature(public_key, message, signature)


def _verify_block_quorum(block: Block,
                         validator_metadata: dict[str, dict[str, Any]]) -> bool:
    """Verify the block's federation signature using Ed25519.

    Extracts the signer ID and signature from the block's
    consensus_finalization event, looks up the signer's public key,
    and verifies the Ed25519 signature against the block hash.

    Args:
        block: Block to verify.
        validator_metadata: Dict mapping validator IDs to metadata dicts
                            (must contain "public_key" hex string).

    Returns:
        True if the signature is valid or no signature is present,
        False if the signature is invalid.
    """
    signer_id = _extract_signer_id(block)
    if not signer_id:
        logger.warning("Block %d has no signer ID — quorum verification skipped", block.index)
        return True

    events = block.to_event_list()
    for event in reversed(events):
        if event.get("event") == "consensus_finalization":
            signature = event.get("details", {}).get("signature", "")
            break
    else:
        logger.warning("Block %d has no consensus_finalization event", block.index)
        return True

    if not signature:
        logger.warning("Block %d has empty federation signature", block.index)
        return True

    public_key = validator_metadata.get(signer_id, {}).get("public_key")
    if not public_key:
        logger.warning(
            "Block %d signer %s has no public_key in metadata — skipping sig verify",
            block.index, signer_id
        )
        return True

    message = block.hash.encode("utf-8")
    is_valid = verify_signature(public_key, message, signature)
    if not is_valid:
        logger.error(
            "Block %d federation signature INVALID for signer %s",
            block.index, signer_id
        )
    return is_valid
