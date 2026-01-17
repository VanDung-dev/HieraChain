"""
Zero Knowledge Proof Verifier for HieraChain Framework.

This module implements the ZKVerifier class that verifies ZK proofs from SubChains
to ensure state transitions are mathematically correct, preventing Fake Proofs.

Supports two modes:
- Mock: Uses SHA-256 hash comparison for development/testing.
- Production: Integrates with ZoKrates or external proving service.
"""

import hashlib
import json
import logging
from typing import Any
from dataclasses import dataclass

from hierachain.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ZKPublicInputs:
    """
    Public inputs for ZK proof verification.
    
    These are the values that both Prover and Verifier can see.
    """
    old_state_root: str
    new_state_root: str
    block_index: int
    sub_chain_name: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "old_state_root": self.old_state_root,
            "new_state_root": self.new_state_root,
            "block_index": self.block_index,
            "sub_chain_name": self.sub_chain_name
        }
    
    def to_bytes(self) -> bytes:
        """Serialize to bytes for hashing."""
        return json.dumps(self.to_dict(), sort_keys=True).encode('utf-8')
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZKPublicInputs":
        """Create from dictionary."""
        return cls(
            old_state_root=data.get("old_state_root", ""),
            new_state_root=data.get("new_state_root", ""),
            block_index=data.get("block_index", 0),
            sub_chain_name=data.get("sub_chain_name", "")
        )


class ZKVerificationError(Exception):
    """Exception raised when ZK proof verification fails."""
    pass


class ZKVerifier:
    """
    Zero Knowledge Proof Verifier for MainChain.
    
    Responsibilities:
    - Verify ZK proofs from SubChains.
    - Reject invalid state transitions (Fake Proofs).
    - Support both Mock and Production modes.
    
    Usage:
        verifier = ZKVerifier(mode="mock")
        is_valid = verifier.verify(proof_bytes, public_inputs)
    """
    
    def __init__(self, mode: str | None = None):
        """
        Initialize ZK Verifier.
        
        Args:
            mode: Verification mode ("mock" or "production").
                  Defaults to settings.ZK_MODE if not specified.
        """
        self.mode = mode or getattr(settings, 'ZK_MODE', 'mock')
        self.verification_key: bytes | None = None
        self.stats = {
            "total_verifications": 0,
            "successful_verifications": 0,
            "failed_verifications": 0
        }
        
        # Load verification key for production mode
        if self.mode == "production":
            self._load_verification_key()
        
        logger.info(f"ZKVerifier initialized in '{self.mode}' mode")
    
    def verify(self, proof: bytes, public_inputs: dict[str, Any] | ZKPublicInputs) -> bool:
        """
        Verify a ZK proof.
        
        Args:
            proof: Serialized ZK proof bytes.
            public_inputs: Dict or ZKPublicInputs containing:
                - old_state_root: Merkle root of previous state.
                - new_state_root: Merkle root of new state.
                - block_index: Block index (prevents replay attacks).
        
        Returns:
            True if proof is valid, False otherwise.
        
        Raises:
            ZKVerificationError: If verification encounters an error.
        """
        self.stats["total_verifications"] += 1
        
        # Normalize public inputs
        if isinstance(public_inputs, dict):
            inputs = ZKPublicInputs.from_dict(public_inputs)
        else:
            inputs = public_inputs
        
        # Validate public inputs
        if not self._validate_public_inputs(inputs):
            logger.warning("Invalid public inputs provided for ZK verification")
            self.stats["failed_verifications"] += 1
            return False
        
        try:
            if self.mode == "mock":
                result = self._verify_mock(proof, inputs)
            elif self.mode == "production":
                result = self._verify_production(proof, inputs)
            else:
                raise ZKVerificationError(f"Unknown verification mode: {self.mode}")
            
            if result:
                self.stats["successful_verifications"] += 1
                logger.debug(f"ZK Proof verified successfully for block {inputs.block_index}")
            else:
                self.stats["failed_verifications"] += 1
                logger.warning(f"ZK Proof verification FAILED for block {inputs.block_index}")
            
            return result
            
        except Exception as e:
            self.stats["failed_verifications"] += 1
            logger.error(f"ZK Verification error: {e}")
            raise ZKVerificationError(f"Verification failed: {e}") from e
    
    def _verify_mock(self, proof: bytes, public_inputs: ZKPublicInputs) -> bool:
        """
        Mock verification using SHA-256 hash comparison.
        
        This mode is for development and testing only.
        It verifies that the proof matches the expected hash of public inputs.
        
        Args:
            proof: Proof bytes (expected to be a SHA-256 hash).
            public_inputs: Public inputs to verify against.
        
        Returns:
            True if proof matches expected hash.
        """
        # Mock proof format: magic_bytes + sha256(public_inputs_json)
        magic_bytes = b"mock_proof"
        
        # 1. Check Magic Bytes
        if not proof.startswith(magic_bytes):
            logger.warning("Mock proof missing magic bytes prefix")
            return False
            
        # 2. Extract Hash
        if len(proof) < len(magic_bytes) + 32:
            logger.warning("Mock proof too short")
            return False
            
        proof_hash = proof[len(magic_bytes):len(magic_bytes) + 32]
        
        # 3. Compute Expected Hash (from JSON bytes)
        expected_hash = hashlib.sha256(public_inputs.to_bytes()).digest()
        
        return proof_hash == expected_hash
    
    def _verify_production(self, proof: bytes, public_inputs: ZKPublicInputs) -> bool:
        """
        Production verification using ZoKrates or external service.
        
        Args:
            proof: Serialized ZK-SNARK proof.
            public_inputs: Public inputs for verification.
        
        Returns:
            True if proof is valid according to ZK circuit.
        
        Raises:
            NotImplementedError: Production mode not yet implemented.
        """
        raise NotImplementedError(
            "Production ZK verification not yet implemented. "
            "See ZK_PROOF_ARCHITECTURE.md Section 4.2 for implementation details."
        )
    
    def _validate_public_inputs(self, inputs: ZKPublicInputs) -> bool:
        """
        Validate that public inputs are well-formed.
        
        Args:
            inputs: Public inputs to validate.
        
        Returns:
            True if inputs are valid.
        """
        # Check old_state_root is a valid hash (64 hex chars for SHA-256)
        if not inputs.old_state_root or len(inputs.old_state_root) < 16:
            logger.debug(f"Invalid old_state_root: {inputs.old_state_root}")
            return False
        
        # Check new_state_root is a valid hash
        if not inputs.new_state_root or len(inputs.new_state_root) < 16:
            logger.debug(f"Invalid new_state_root: {inputs.new_state_root}")
            return False
        
        # Check block_index is non-negative
        if inputs.block_index < 0:
            logger.debug(f"Invalid block_index: {inputs.block_index}")
            return False
        
        return True
    
    def _load_verification_key(self) -> None:
        """Load verification key from configured path."""
        key_path = getattr(settings, 'ZK_VERIFICATION_KEY_PATH', '')
        
        if not key_path:
            logger.warning("ZK_VERIFICATION_KEY_PATH not configured")
            return
        
        try:
            with open(key_path, 'rb') as f:
                self.verification_key = f.read()
            logger.info(f"Loaded verification key from {key_path}")
        except FileNotFoundError:
            logger.error(f"Verification key not found at {key_path}")
        except Exception as e:
            logger.error(f"Error loading verification key: {e}")
    
    def get_stats(self) -> dict[str, int]:
        """
        Get verification statistics.
        
        Returns:
            Dictionary containing verification counts.
        """
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset verification statistics."""
        self.stats = {
            "total_verifications": 0,
            "successful_verifications": 0,
            "failed_verifications": 0
        }


# Singleton instance for global access
_default_verifier: ZKVerifier | None = None


def get_zk_verifier() -> ZKVerifier:
    """
    Get the default ZKVerifier instance.
    
    Creates a new instance if one doesn't exist.
    
    Returns:
        ZKVerifier instance.
    """
    global _default_verifier
    if _default_verifier is None:
        _default_verifier = ZKVerifier()
    return _default_verifier


def verify_zk_proof(proof: bytes, public_inputs: dict[str, Any]) -> bool:
    """
    Convenience function to verify a ZK proof.
    
    Args:
        proof: Serialized ZK proof bytes.
        public_inputs: Dict containing old_state_root, new_state_root, block_index.
    
    Returns:
        True if proof is valid, False otherwise.
    """
    verifier = get_zk_verifier()
    return verifier.verify(proof, public_inputs)
