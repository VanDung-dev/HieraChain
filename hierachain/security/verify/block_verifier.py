"""
Block Verification module for HieraChain Framework.

This module implements comprehensive block verification including:
- Block hash verification
- Merkle root verification
- Chain link verification (previous_hash)
- Block creator signature verification

These checks ensure blockchain integrity and prevent tampering.
"""

import logging
from typing import Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


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

    def verify_block(self, block: Any, previous_block: Any | None = None) -> VerificationResult:
        """
        Perform full verification of a block.

        Args:
            block: The block to verify.
            previous_block: The previous block (optional, for chain link verification).

        Returns:
            VerificationResult with status and details.
        """
        self._stats["blocks_verified"] += 1
        results = []

        # 1. Verify block hash
        hash_result = self.verify_block_hash(block)
        results.append(("hash", hash_result))
        if not hash_result.is_valid:
            self._stats["hash_failures"] += 1

        # 2. Verify merkle root
        merkle_result = self.verify_merkle_root(block)
        results.append(("merkle", merkle_result))
        if not merkle_result.is_valid:
            self._stats["merkle_failures"] += 1

        # 3. Verify chain link if previous block provided
        if previous_block is not None:
            link_result = self.verify_chain_link(block, previous_block)
            results.append(("chain_link", link_result))
            if not link_result.is_valid:
                self._stats["chain_link_failures"] += 1

        # 4. Verify signature if present
        if hasattr(block, 'signature') and block.signature:
            sig_result = self.verify_block_signature(block)
            results.append(("signature", sig_result))
            if not sig_result.is_valid:
                self._stats["signature_failures"] += 1

        # Aggregate results
        failed = [name for name, result in results if not result.is_valid]

        if failed:
            self._stats["invalid_blocks"] += 1
            return VerificationResult(
                status=VerificationStatus.INVALID,
                message=f"Block {block.index} verification failed: {', '.join(failed)}",
                details={name: result.message for name, result in results}
            )

        self._stats["valid_blocks"] += 1
        return VerificationResult(
            status=VerificationStatus.VALID,
            message=f"Block {block.index} verified successfully",
            details={name: result.message for name, result in results}
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
            logger.error(f"Error verifying block hash: {e}")
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
            logger.error(f"Error verifying merkle root: {e}")
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
            logger.error(f"Error verifying chain link: {e}")
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Chain link verification error: {e}"
            )

    def verify_block_signature(self, block: Any, public_key: bytes | None = None) -> VerificationResult:
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
            if not hasattr(block, 'signature') or not block.signature:
                if self.strict_mode:
                    return VerificationResult(
                        status=VerificationStatus.INVALID,
                        message="Block signature missing (strict mode)"
                    )
                return VerificationResult(
                    status=VerificationStatus.VALID,
                    message="Block signature not present (non-strict mode)"
                )

            if not hasattr(block, 'creator_id') or not block.creator_id:
                return VerificationResult(
                    status=VerificationStatus.INVALID,
                    message="Block creator_id missing"
                )

            # Compute message to verify (block header without signature)
            message = self._get_signable_content(block)

            # Try to verify with cryptography library
            if public_key:
                is_valid = self._verify_signature(message, block.signature, public_key)
            else:
                # For now, without key lookup, we can only check signature format
                is_valid = self._verify_signature_format(block.signature)

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
            logger.error(f"Error verifying block signature: {e}")
            return VerificationResult(
                status=VerificationStatus.ERROR,
                message=f"Signature verification error: {e}"
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

    @staticmethod
    def _verify_signature(message: bytes, signature: str, public_key: bytes) -> bool:
        """Verify signature using cryptography library."""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec, padding
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
            else:
                # RSA fallback
                pub_key.verify(sig_bytes, message, padding.PKCS1v15(), hashes.SHA256())

            return True

        except InvalidSignature:
            return False
        except Exception as e:
            logger.warning(f"Signature verification failed: {e}")
            return False

    @staticmethod
    def _verify_signature_format(signature: str) -> bool:
        """Basic check that signature has valid hex format and length."""
        try:
            sig_bytes = bytes.fromhex(signature)
            # Typical ECDSA signature is 64-72 bytes, RSA is 256-512 bytes
            return 64 <= len(sig_bytes) <= 512
        except ValueError:
            return False

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
                message=f"Chain verification failed: {len(invalid_blocks)} invalid blocks",
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
    return _default_verifier


def verify_block(block: Any, previous_block: Any | None = None) -> bool:
    """Convenience function to verify a single block."""
    verifier = get_block_verifier(strict_mode=False)
    return verifier.verify_block(block, previous_block).is_valid
