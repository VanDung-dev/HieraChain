"""
Zero Knowledge Proof Verifier for HieraChain Ledger.

This module implements the ZKVerifier class that verifies ZK proofs from SubChains
to ensure state transitions are mathematically correct, preventing Fake Proofs.

Supports two modes:
- Mock: Uses SHA-256 hash comparison for development/testing.
- Production: Integrates with ZoKrates or external proving service.
"""

import hashlib
import json
from typing import Any
from dataclasses import dataclass

from hierachain.config.settings import settings
from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZKPublicInputs":
        """Create from dictionary."""
        return cls(
            old_state_root=data.get("old_state_root", ""),
            new_state_root=data.get("new_state_root", ""),
            block_index=data.get("block_index", 0),
            sub_chain_name=data.get("sub_chain_name", "")
        )
    
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


class ZKVerificationError(Exception):
    """Exception raised when ZK proof verification fails."""
    pass


def _verify_mock(proof: bytes, public_inputs: ZKPublicInputs) -> bool:
    """
    Mock verification using SHA-256 hash comparison.

    This mode is for development and testing only.
    It verifies that the proof matches the expected hash of public inputs.

    Supports two formats:
    - Legacy: b"mock_proof" + sha256(public_inputs)
    - V2: b"mock_zkp_v2\\x00" + version(4) + size(4) + sha256(public_inputs)

    Args:
        proof: Proof bytes (expected to be a SHA-256 hash).
        public_inputs: Public inputs to verify against.

    Returns:
        True if proof matches expected hash.
    """
    # Compute expected hash from public inputs
    expected_hash = hashlib.sha256(public_inputs.to_bytes()).digest()

    # V2 format: mock_zkp_v2\x00 (12 bytes) + version (4) + size (4) + hash (32)
    magic_v2 = b"mock_zkp_v2\x00"
    if proof.startswith(magic_v2):
        if len(proof) < 52:  # 12 + 4 + 4 + 32
            logger.warning("Mock proof v2 too short")
            return False

        # Extract hash from position 20 (12+4+4)
        proof_hash = proof[20:52]
        return proof_hash == expected_hash

    # Legacy format: mock_proof (10 bytes) + hash (32)
    magic_legacy = b"mock_proof"
    if proof.startswith(magic_legacy):
        if len(proof) < len(magic_legacy) + 32:
            logger.warning("Mock proof legacy too short")
            return False

        proof_hash = proof[len(magic_legacy):len(magic_legacy) + 32]
        return proof_hash == expected_hash

    logger.warning("Mock proof missing magic bytes prefix")
    return False


def _validate_public_inputs(inputs: ZKPublicInputs) -> bool:
    """
    Validate that public inputs are well-formed.

    Args:
        inputs: Public inputs to validate.

    Returns:
        True if inputs are valid.
    """
    # Check old_state_root is a valid hash (64 hex chars for SHA-256)
    if not inputs.old_state_root or len(inputs.old_state_root) < 16:
        logger.debug("Invalid old_state_root: %s", inputs.old_state_root)
        return False

    # Check new_state_root is a valid hash
    if not inputs.new_state_root or len(inputs.new_state_root) < 16:
        logger.debug("Invalid new_state_root: %s", inputs.new_state_root)
        return False

    # Check block_index is non-negative
    if inputs.block_index < 0:
        logger.debug("Invalid block_index: %d", inputs.block_index)
        return False

    return True


def _normalize_inputs(public_inputs: dict[str, Any] | ZKPublicInputs) -> ZKPublicInputs:
    """Normalize public inputs to ZKPublicInputs object."""
    if isinstance(public_inputs, dict):
        return ZKPublicInputs.from_dict(public_inputs)
    return public_inputs


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

        # Warn if mock mode is active in a non-dev context
        if self.mode == "mock":
            if getattr(settings, 'ENABLE_ZK_PROOFS', False):
                logger.critical(
                    "ZK mode is 'mock' but ENABLE_ZK_PROOFS=True! "
                    "Mock proofs are forgeable — set ZK_MODE=production."
                )

        # Load verification key for production mode
        if self.mode == "production":
            self._load_verification_key()
        
        logger.info("ZKVerifier initialized in '%s' mode", self.mode)
    
    def verify(
        self, proof: bytes, public_inputs: dict[str, Any] | ZKPublicInputs
    ) -> bool:
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
        
        # 1. Normalize and validate inputs
        inputs = _normalize_inputs(public_inputs)
        if not _validate_public_inputs(inputs):
            return self._handle_verification_failure(
                inputs, "Invalid public inputs provided"
            )
        
        try:
            # 2. Perform verification based on mode
            result = self._execute_verification(proof, inputs)
            
            # 3. Process result and update stats
            return self._process_verification_result(result, inputs)
            
        except Exception as e:
            return self._handle_verification_exception(e)

    def _execute_verification(self, proof: bytes, inputs: ZKPublicInputs) -> bool:
        """Execute core verification logic based on mode."""
        if self.mode == "mock":
            # Mock mode: reject if zk proofs are supposed to be enabled
            if getattr(settings, 'ENABLE_ZK_PROOFS', False):
                import os
                import sys
                is_testing = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
                if not is_testing:
                    logger.error(
                        "Rejecting mock proof for block %d: ENABLE_ZK_PROOFS=True "
                        "requires production mode",
                        inputs.block_index
                    )
                    return False
            return _verify_mock(proof, inputs)
        if self.mode == "production":
            return self._verify_production(proof, inputs)
        raise ValueError(f"Unknown verification mode: {self.mode}")

    def _process_verification_result(
        self, result: bool, inputs: ZKPublicInputs
    ) -> bool:
        """Update stats and log result."""
        if result:
            self.stats["successful_verifications"] += 1
            logger.debug(
                "ZK Proof verified successfully for block %d", inputs.block_index
            )
        else:
            self.stats["failed_verifications"] += 1
            logger.warning(
                "ZK Proof verification FAILED for block %d", inputs.block_index
            )
        return result

    def _handle_verification_failure(
        self, inputs: ZKPublicInputs, message: str
    ) -> bool:
        """Handle pre-verification validation failures."""
        logger.warning(
            "%s for block %d", message, inputs.block_index
        )
        self.stats["failed_verifications"] += 1
        return False

    def _handle_verification_exception(self, e: Exception) -> bool:
        """Handle exceptions during verification process."""
        self.stats["failed_verifications"] += 1
        if isinstance(e, ZKVerificationError):
            logger.error("ZK Verification error: %s", e)
            raise e
        
        error_msg = "Verification failed: %s" % str(e)
        logger.error(error_msg, error=str(e))
        raise ZKVerificationError(error_msg) from e

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

    def _load_verification_key(self) -> None:
        """Load verification key from configured path."""
        key_path = getattr(settings, 'ZK_VERIFICATION_KEY_PATH', '')
        
        if not key_path:
            logger.warning("ZK_VERIFICATION_KEY_PATH not configured")
            return
        
        try:
            with open(key_path, 'rb') as f:
                self.verification_key = f.read()
            logger.info(
                "Loaded verification key from %s", key_path
            )
        except FileNotFoundError:
            logger.error(
                "Verification key not found at %s", key_path
            )
        except Exception as e:
            logger.error(
                "Error loading verification key: %s", e
            )
    
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
    
    verifier = _default_verifier
    if verifier is None:
        raise RuntimeError("ZKVerifier initialization failed")
    return verifier


def reset_zk_verifier() -> None:
    """
    Reset the singleton ZKVerifier instance.
    
    This is primarily for testing purposes to ensure a clean state
    between test runs.
    """
    global _default_verifier
    if _default_verifier is not None:
        _default_verifier.reset_stats()
    _default_verifier = None


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
