"""
Main Chain class implementation for HieraChain Ledger.
"""

import time
import logging
from typing import Any

from hierachain.core.blockchain import Blockchain
from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.consensus.proof_of_federation import ProofOfFederation
from hierachain.core.utils import (
    sanitize_metadata_for_main_chain, validate_proof_metadata,
)
from hierachain.core.block import Block
from hierachain.config.settings import settings
from hierachain.security.verify.zk_verifier import ZKVerifier

from hierachain.hierarchical.main_chain.proofs import (
    _is_valid_hash_format,
    _record_proof_on_main_chain,
    _verify_proof_in_main_chain,
    _get_proofs_by_sub_chain_from_main_chain,
    _verify_zk_proof_helper,
)
from hierachain.hierarchical.main_chain.registry import (
    _get_sub_chain_summary_from_main_chain,
    _get_main_chain_stats_for_chain,
    _get_hierarchical_integrity_report_for_chain,
)

logger = logging.getLogger(__name__)


class MainChain(Blockchain):
    """
    Main Chain implementation for the HieraChain Ledger.

    The Main Chain acts as the root authority (like a CEO in an organization) and:
    - Only stores proofs from Sub-Chains, NOT detailed domain data
    - Maintains the integrity of the entire hierarchical system
    - Provides proof verification and chain coordination
    - Uses Proof of Authority consensus suitable for business applications
    """
    __slots__ = (
        'consensus', 'registered_sub_chains', 'sub_chain_metadata',
        'proof_count', 'latest_proofs', 'recent_proofs',
        'proof_index', 'zk_verifier',
    )

    def __init__(self, name: str = "MainChain", consensus_type: str | None = None):
        """
        Initialize the Main Chain.

        Args:
            name: Name identifier for the Main Chain
            consensus_type: Optional consensus type override ("proof_of_authority" or "proof_of_federation")
        """
        super().__init__(name)

        # Dynamic Consensus Loading
        target_consensus = consensus_type or settings.MAINCHAIN_CONSENSUS
        if target_consensus == "proof_of_federation":
            self.consensus = ProofOfFederation("MainChain_PoF")
        else:
            # Default back to PoA
            self.consensus = ProofOfAuthority("MainChain_PoA", block_interval=settings.BLOCK_INTERVAL)

        self.registered_sub_chains: set[str] = set()
        self.sub_chain_metadata: dict[str, dict[str, Any]] = {}
        self.proof_count: int = 0
        self.latest_proofs: dict[str, dict[str, Any]] = {}
        self.recent_proofs: list[dict[str, Any]] = []
        self.proof_index: dict[str, list[int]] = {}  # sub_chain_name -> block_indices

        # ZK Proof Verifier (initialized if ZK proofs are enabled)
        self.zk_verifier: ZKVerifier | None = None
        if settings.ENABLE_ZK_PROOFS:
            self.zk_verifier = ZKVerifier(mode=settings.ZK_MODE)
            logger.info(
                "MainChain initialized with ZK Verification in '%s' mode",
                settings.ZK_MODE,
            )

        # Register Main Chain as the primary authority/validator
        if hasattr(self.consensus, "add_authority"):
            self.consensus.add_authority(
                "main_chain",
                {
                    "role": "root_authority",
                    "permissions": ["proof_validation", "sub_chain_registration"],
                    "created_at": time.time(),
                },
            )

    def is_valid_new_block(self, block) -> bool:
        """
        Validate a new block including consensus rules.

        Args:
            block: Block to validate

        Returns:
            True if block is valid, False otherwise
        """
        # 1. Base structural validation
        if not super().is_valid_new_block(block):
            return False

        # 2. Consensus validation
        previous_block = self.get_latest_block()

        if not self.consensus.validate_block(block, previous_block):
            return False

        return True

    def register_sub_chain(
        self, sub_chain_name: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """
        Register a Sub-Chain with the Main Chain.

        Args:
            sub_chain_name: Name of the Sub-Chain to register
            metadata: Metadata about the Sub-Chain

        Returns:
            True if Sub-Chain was registered successfully, False otherwise
        """
        if sub_chain_name in self.registered_sub_chains:
            return False

        self.registered_sub_chains.add(sub_chain_name)
        self.sub_chain_metadata[sub_chain_name] = metadata or {}

        # Add Sub-Chain as an authority for proof submission
        self.consensus.add_authority(sub_chain_name, {
            "role": "sub_chain",
            "permissions": ["proof_submission"],
            "registered_at": time.time(),
            "metadata": metadata
        })

        # Create registration event
        registration_event = {
            "entity_id": sub_chain_name,
            "event": "sub_chain_registration",
            "timestamp": time.time(),
            "details": {
                "sub_chain_name": sub_chain_name,
                "registered_by": "main_chain",
                "metadata": sanitize_metadata_for_main_chain(metadata or {})
            }
        }

        self.add_event(registration_event)
        return True

    def add_proof(
        self,
        sub_chain_name: str,
        proof_hash: str,
        metadata: dict[str, Any] | None,
        zk_proof: bytes | None = None
    ) -> bool:
        """
        Add a proof from a Sub-Chain to the Main Chain.

        This is the critical method that follows Ledger guidelines:
        - Only stores proof evidence, NOT domain data
        - Metadata contains summary data only
        - NOW WITH ZK PROOF VERIFICATION for trustless security

        Args:
            sub_chain_name: Name of the Sub-Chain submitting the proof
            proof_hash: Hash of the block being proven
            metadata: Summary metadata (NOT detailed domain data)
            zk_proof: Optional ZK proof bytes for trustless verification

        Returns:
            True if proof was added successfully, False otherwise
        """
        if sub_chain_name not in self.registered_sub_chains:
            logger.warning(
                "Rejected proof: SubChain '%s' not registered",
                sub_chain_name,
            )
            return False

        if not isinstance(metadata, dict):
            logger.warning(
                "Rejected proof: Invalid metadata type from '%s'",
                sub_chain_name,
            )
            return False

        if not validate_proof_metadata(metadata):
            logger.warning(
                "Rejected proof: Invalid metadata from '%s'",
                sub_chain_name,
            )
            return False

        # Validate proof_hash is a proper SHA-256 hex digest
        if not _is_valid_hash_format(proof_hash):
            logger.warning(
                "Rejected proof: Invalid proof_hash format from '%s'",
                sub_chain_name,
            )
            return False

        # === ZK PROOF VERIFICATION ===
        zk_verified = self._verify_zk_proof(
            sub_chain_name, proof_hash, metadata, zk_proof
        )
        if settings.ENABLE_ZK_PROOFS and zk_proof is not None and not zk_verified:
            return False

        # Sanitize metadata to ensure only summary data
        sanitized_metadata = sanitize_metadata_for_main_chain(metadata)

        # Record proof and update state
        return _record_proof_on_main_chain(
            self, sub_chain_name, proof_hash, sanitized_metadata, zk_verified
        )

    def _verify_zk_proof(
        self,
        sub_chain_name: str,
        proof_hash: str,
        metadata: dict[str, Any],
        zk_proof: bytes | None
    ) -> bool:
        """Verify ZK proof if enabled and provided."""
        return _verify_zk_proof_helper(
            self.zk_verifier, sub_chain_name, proof_hash, metadata, zk_proof
        )

    def verify_proof(self, proof_hash: str, sub_chain_name: str) -> bool:
        """
        Verify a proof exists in the Main Chain.

        Args:
            proof_hash: Hash of the proof to verify
            sub_chain_name: Name of the Sub-Chain that submitted the proof

        Returns:
            True if proof exists and is valid, False otherwise
        """
        return _verify_proof_in_main_chain(self, proof_hash, sub_chain_name)

    def get_proofs_by_sub_chain(self, sub_chain_name: str) -> list[dict[str, Any]]:
        """
        Get all proofs submitted by a specific Sub-Chain.

        Args:
            sub_chain_name: Name of the Sub-Chain

        Returns:
            List of proof events from the specified Sub-Chain
        """
        return _get_proofs_by_sub_chain_from_main_chain(self, sub_chain_name)

    def get_sub_chain_summary(self, sub_chain_name: str) -> dict[str, Any]:
        """
        Get summary information about a Sub-Chain.

        Args:
            sub_chain_name: Name of the Sub-Chain

        Returns:
            Summary information about the Sub-Chain
        """
        return _get_sub_chain_summary_from_main_chain(self, sub_chain_name)

    def finalize_block(self) -> "Block | None":
        """
        Finalize pending events into a new block using consensus.
        Overridden from base Blockchain to ensure PoA/PoF compliance.

        Returns:
            The newly created and added block, or None if no pending events
        """
        with self.lock:
            if not self.pending_events:
                return None

            # Create block with pending events
            events = self.pending_events.copy()
            new_block = self.create_block(events)

            # Finalize block using PoA consensus
            finalized_block = self.consensus.finalize_block(new_block, "main_chain")

            # Add finalized block to chain
            if finalized_block and self.add_block(finalized_block):
                self.pending_events = self.pending_events[len(events):]
                return finalized_block

            return None

    def get_main_chain_stats(self) -> dict[str, Any]:
        """
        Get comprehensive statistics about the Main Chain.

        Returns:
            Dictionary containing Main Chain statistics
        """
        return _get_main_chain_stats_for_chain(self)

    def finalize_main_chain_block(self) -> dict[str, Any] | None:
        """
        Finalize a block on the Main Chain using PoA consensus.

        Returns:
            Information about the finalized block, or None if no pending events
        """
        with self.lock:
            if not self.pending_events:
                return None

            # Create block with pending events
            events = self.pending_events.copy()
            new_block = self.create_block(events)

            # Finalize block using PoA consensus
            finalized_block = self.consensus.finalize_block(new_block, "main_chain")

            # Add finalized block to chain
            if finalized_block and self.add_block(finalized_block):
                self.pending_events = self.pending_events[len(events):]
                return {
                    "block_index": finalized_block.index,
                    "block_hash": finalized_block.hash,
                    "events_count": len(finalized_block.events),
                    "finalized_at": time.time()
                }

            return None

    def validate_sub_chain_proof_format(self, proof_data: dict[str, Any]) -> bool:
        """
        Validate the format of a Sub-Chain proof submission.

        Args:
            proof_data: Proof data to validate

        Returns:
            True if proof format is valid, False otherwise
        """
        required_fields = ["sub_chain_name", "proof_hash", "metadata"]

        for field in required_fields:
            if field not in proof_data:
                return False

        # Validate Sub-Chain is registered
        if proof_data["sub_chain_name"] not in self.registered_sub_chains:
            return False

        # Validate metadata doesn't contain detailed domain data
        if not validate_proof_metadata(proof_data["metadata"]):
            return False

        return True

    def get_hierarchical_integrity_report(self) -> dict[str, Any]:
        """
        Generate an integrity report for the entire hierarchical system.

        Returns:
            Comprehensive integrity report
        """
        return _get_hierarchical_integrity_report_for_chain(self)

    def __str__(self) -> str:
        """String representation of the Main Chain."""
        return (
            f"MainChain(blocks={len(self.chain)}, "
            f"sub_chains={len(self.registered_sub_chains)}, proofs={self.proof_count})"
        )

    def __repr__(self) -> str:
        """Detailed string representation of the Main Chain."""
        return (
            f"MainChain(name={self.name}, blocks={len(self.chain)}, "
            f"sub_chains={len(self.registered_sub_chains)}, proofs={self.proof_count}, "
            f"valid={self.is_chain_valid()})"
        )
