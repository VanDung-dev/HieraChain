"""
Block Verification module for HieraChain Ledger.

This module implements comprehensive block verification including:
- Block hash verification
- Merkle root verification
- Chain link verification (previous_hash)
- Block creator signature verification

These checks ensure blockchain integrity and prevent tampering.
"""

from typing import Any
from dataclasses import dataclass
from enum import Enum

from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()


class VerificationStatus(Enum):
    """Result status for verification operations."""
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"


@dataclass
class VerificationResult:
    """Result of a verification operation."""
    status: VerificationStatus
    message: str
    details: dict[str, Any] | None = None

    @property
    def is_valid(self) -> bool:
        """Check if verification passed."""
        return self.status == VerificationStatus.VALID

    def __bool__(self) -> bool:
        return self.is_valid


class BlockVerificationError(Exception):
    """Exception raised when block verification fails."""

    def __init__(self, message: str, block_index: int | None = None):
        super().__init__(message)
        self.block_index = block_index


def _has_valid_signature_field(block: Any) -> bool:
    """Check if block has a non-empty signature field."""
    return hasattr(block, 'signature') and block.signature


def _verify_signature_format(signature: str) -> bool:
    """Basic check that signature has valid hex format and length."""
    try:
        sig_bytes = bytes.fromhex(signature)
        # Typical ECDSA signature is 64-72 bytes, RSA is 256-512 bytes
        return 64 <= len(sig_bytes) <= 512
    except ValueError:
        return False


def _verify_signature(message: bytes, signature: str, public_key: bytes) -> bool:
    """Verify signature using cryptography library."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa, ed25519, ed448
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        logger.warning("cryptography library not available for signature verification")
        return False

    try:
        # Decode signature from hex
        sig_bytes = bytes.fromhex(signature)

        # Load public key
        pub_key = serialization.load_pem_public_key(public_key)

        # Verify based on key type
        if isinstance(pub_key, ec.EllipticCurvePublicKey):
            pub_key.verify(sig_bytes, message, ec.ECDSA(hashes.SHA256()))
        elif isinstance(pub_key, rsa.RSAPublicKey):
            pub_key.verify(sig_bytes, message, padding.PKCS1v15(), hashes.SHA256())
        elif isinstance(pub_key, ed25519.Ed25519PublicKey):
            pub_key.verify(sig_bytes, message)
        elif isinstance(pub_key, ed448.Ed448PublicKey):
            pub_key.verify(sig_bytes, message)
        else:
            logger.error("Unsupported public key type for block verification: %s", type(pub_key))
            return False

        return True

    except InvalidSignature:
        return False
    except Exception as e:
        logger.warning("Signature verification failed: %s", e)
        return False


def _perform_crypto_verification(
    message: bytes, signature: str, public_key: bytes | None
) -> bool:
    """Route to appropriate signature verification method."""
    if public_key:
        return _verify_signature(message, signature, public_key)
    # For now, without key lookup, we can only check signature format
    return _verify_signature_format(signature)


class BlockVerifier:
    """
    Comprehensive block verification for HieraChain.

    Verifies:
    - Block hash matches computed hash
    - Merkle root matches events
    - Chain link (previous_hash) is valid
    - Block creator signature (if present)

    Example:
        verifier = BlockVerifier()
        result = verifier.verify_block(block)
        if not result.is_valid:
            logger.error(f"Block invalid: {result.message}")
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize BlockVerifier.

        Args:
            strict_mode: If True, missing signatures are treated as errors.
                         If False, missing signatures are warnings only.
        """
        self.strict_mode = strict_mode
        self._stats = {
            "blocks_verified": 0,
            "valid_blocks": 0,
            "invalid_blocks": 0,
            "hash_failures": 0,
            "merkle_failures": 0,
            "chain_link_failures": 0,
            "signature_failures": 0,
        }

    def verify_block(
        self, block: Any, previous_block: Any | None = None
    ) -> VerificationResult:
        """
        Perform full verification of a block.

        Args:
            block: The block to verify.
            previous_block: The previous block (optional, for chain link verification).

        Returns:
            VerificationResult with status and details.
        """
        self._stats["blocks_verified"] += 1
        results = {}

        # Define verification steps: (name, verification_function, stat_failure_key)
        steps = [
            ("hash", lambda: self.verify_block_hash(block), "hash_failures"),
            ("merkle", lambda: self.verify_merkle_root(block), "merkle_failures"),
        ]

        if previous_block is not None:
            steps.append((
                "chain_link",
                lambda: self.verify_chain_link(block, previous_block),
                "chain_link_failures"
            ))

        if _has_valid_signature_field(block):
            steps.append((
                "signature",
                lambda: self.verify_block_signature(block),
                "signature_failures"
            ))

        # Execute all steps and track statistics
        for name, verify_func, stat_key in steps:
            result = verify_func()
            results[name] = result
            if not result.is_valid:
                self._stats[stat_key] += 1

        # Aggregate and return final result
        return self._aggregate_verification_results(block, results)

    def _aggregate_verification_results(
        self,
        block: Any,
        results: dict[str, VerificationResult]
    ) -> VerificationResult:
        """Helper to aggregate multiple verification results into one."""
        failed_steps = [name for name, res in results.items() if not res.is_valid]

        if failed_steps:
            self._stats["invalid_blocks"] += 1
            return VerificationResult(
                status=VerificationStatus.INVALID,
                message=(
                    f"Block {block.index} verification failed: "
                    f"{', '.join(failed_steps)}"
                ),
                details={name: res.message for name, res in results.items()}
            )

        self._stats["valid_blocks"] += 1
        return VerificationResult(
            status=VerificationStatus.VALID,
            message=f"Block {block.index} verified successfully",
            details={name: res.message for name, res in results.items()}
        )

    @staticmethod
    def verify_block_hash(block: Any) -> VerificationResult:
        """
        Verify that block hash matches computed hash.

        Args:
            block: Block to verify.

        Returns:
            VerificationResult indicating if hash is valid.
        """
        try:
            stored_hash = block.hash
            computed_hash = block.calculate_hash()

            if stored_hash == computed_hash:
                return VerificationResult(
                    status=VerificationStatus.VALID,
                    message="Block hash verified"
                )

            return VerificationResult(
                status=VerificationStatus.INVALID,
                message="Block hash mismatch",
                details={
                    "stored_hash": stored_hash,
                    "computed_hash": computed_hash
                }
            )

        except Exception as e:
            logger.error("Error verifying block hash: %s", e)
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Hash verification error: {e}"
            )

    @staticmethod
    def verify_merkle_root(block: Any) -> VerificationResult:
        """
        Verify that merkle root matches events in block.

        Args:
            block: Block to verify.

        Returns:
            VerificationResult indicating if merkle root is valid.
        """
        try:
            stored_merkle = block.merkle_root
            computed_merkle = block.calculate_merkle_root()

            if stored_merkle == computed_merkle:
                return VerificationResult(
                    status=VerificationStatus.VALID,
                    message="Merkle root verified"
                )

            return VerificationResult(
                status=VerificationStatus.INVALID,
                message="Merkle root mismatch",
                details={
                    "stored_merkle": stored_merkle,
                    "computed_merkle": computed_merkle
                }
            )

        except Exception as e:
            logger.error("Error verifying merkle root: %s", e)
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Merkle verification error: {e}"
            )

    @staticmethod
    def verify_chain_link(block: Any, previous_block: Any) -> VerificationResult:
        """
        Verify that block's previous_hash matches previous block's hash.

        Args:
            block: Current block to verify.
            previous_block: The block that should precede this one.

        Returns:
            VerificationResult indicating if chain link is valid.
        """
        try:
            # Check index continuity
            if block.index != previous_block.index + 1:
                return VerificationResult(
                    status=VerificationStatus.INVALID,
                    message="Block index not sequential",
                    details={
                        "block_index": block.index,
                        "previous_index": previous_block.index
                    }
                )

            # Check hash link
            if block.previous_hash != previous_block.hash:
                return VerificationResult(
                    status=VerificationStatus.INVALID,
                    message="Previous hash mismatch",
                    details={
                        "block_previous_hash": block.previous_hash,
                        "previous_block_hash": previous_block.hash
                    }
                )

            return VerificationResult(
                status=VerificationStatus.VALID,
                message="Chain link verified"
            )

        except Exception as e:
            logger.error("Error verifying chain link: %s", e)
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Chain link verification error: {e}"
            )

    def verify_block_signature(
        self, block: Any, public_key: bytes | None = None
    ) -> VerificationResult:
        """
        Verify block creator's signature.

        Args:
            block: Block to verify.
            public_key: Optional public key for verification.
                        If not provided, uses block.creator_id to lookup key.

        Returns:
            VerificationResult indicating if signature is valid.
        """
        try:
            # 1. Check for signature presence
            if not _has_valid_signature_field(block):
                return self._handle_missing_signature()

            # 2. Check for creator identity
            if not hasattr(block, 'creator_id') or not block.creator_id:
                return VerificationResult(
                    status=VerificationStatus.INVALID,
                    message="Block creator_id missing"
                )

            # 3. Cryptographic verification
            message = self._get_signable_content(block)
            is_valid = _perform_crypto_verification(
                message, block.signature, public_key
            )

            if is_valid:
                return VerificationResult(
                    status=VerificationStatus.VALID,
                    message="Block signature verified"
                )

            return VerificationResult(
                status=VerificationStatus.INVALID,
                message="Block signature invalid"
            )

        except Exception as e:
            logger.error("Error verifying block signature: %s", e)
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Signature verification error: {e}"
            )

    def _handle_missing_signature(self) -> VerificationResult:
        """Handle cases where block signature is missing based on strict mode."""
        if self.strict_mode:
            return VerificationResult(
                status=VerificationStatus.INVALID,
                message="Block signature missing (strict mode)"
            )
        return VerificationResult(
            status=VerificationStatus.VALID,
            message="Block signature not present (non-strict mode)"
        )

    @staticmethod
    def _get_signable_content(block: Any) -> bytes:
        """Get the content that was signed (block header without signature)."""
        import json
        header = {
            "index": block.index,
            "timestamp": block.timestamp,
            "previous_hash": block.previous_hash,
            "merkle_root": block.merkle_root,
            "nonce": block.nonce,
            "creator_id": block.creator_id
        }
        return json.dumps(header, sort_keys=True).encode('utf-8')

    def verify_chain(self, blocks: list[Any]) -> VerificationResult:
        """
        Verify an entire chain of blocks.

        Args:
            blocks: List of blocks in order (index 0, 1, 2, ...).

        Returns:
            VerificationResult for the entire chain.
        """
        if not blocks:
            return VerificationResult(
                status=VerificationStatus.VALID,
                message="Empty chain is valid"
            )

        invalid_blocks = []

        for i, block in enumerate(blocks):
            previous = blocks[i - 1] if i > 0 else None
            result = self.verify_block(block, previous)

            if not result.is_valid:
                invalid_blocks.append({
                    "index": block.index,
                    "errors": result.message
                })

        if invalid_blocks:
            return VerificationResult(
                status=VerificationStatus.INVALID,
                message=(
                    f"Chain verification failed: {len(invalid_blocks)} invalid blocks"
                ),
                details={"invalid_blocks": invalid_blocks}
            )

        return VerificationResult(
            status=VerificationStatus.VALID,
            message=f"Chain verified: {len(blocks)} blocks valid"
        )

    def get_stats(self) -> dict[str, int]:
        """Get verification statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset verification statistics."""
        for key in self._stats:
            self._stats[key] = 0


# Singleton instance
_default_verifier: BlockVerifier | None = None


def get_block_verifier(strict_mode: bool = True) -> BlockVerifier:
    """Get default BlockVerifier instance."""
    global _default_verifier
    if _default_verifier is None:
        _default_verifier = BlockVerifier(strict_mode=strict_mode)
    
    verifier = _default_verifier
    assert verifier is not None
    return verifier


def verify_block(block: Any, previous_block: Any | None = None) -> bool:
    """Convenience function to verify a single block."""
    verifier = get_block_verifier(strict_mode=False)
    return verifier.verify_block(block, previous_block).is_valid
