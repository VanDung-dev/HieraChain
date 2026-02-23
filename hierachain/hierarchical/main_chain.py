"""
Main Chain implementation for HieraChain Ledger.

This module implements the Main Chain class that acts as the root authority
in the HieraChain structure. The Main Chain only stores proofs
from Sub-Chains, never detailed domain data, following Ledger guidelines.
"""

import time
import logging
from typing import Any

from hierachain.core.blockchain import Blockchain
from hierachain.core.consensus.proof_of_authority import ProofOfAuthority
from hierachain.core.consensus.proof_of_federation import ProofOfFederation
from hierachain.core.utils import (
    sanitize_metadata_for_main_chain,
    validate_proof_metadata,
)
from hierachain.core.block import Block
from hierachain.config.settings import settings
from hierachain.security.verify.zk_verifier import ZKVerifier, ZKVerificationError

logger = logging.getLogger(__name__)


def _find_proof_in_events(events: list[dict[str, Any]], proof_hash: str, sub_chain_name: str) -> bool:
    """Check if a proof exists in a list of events."""
    for event in events:
        if (
            event.get("event") == "proof_submission"
            and event.get("details", {}).get("proof_hash") == proof_hash
            and event.get("details", {}).get("sub_chain_name") == sub_chain_name
        ):
            return True
    return False


def _filter_proofs_by_sub_chain(events: list[dict[str, Any]], sub_chain_name: str) -> list[dict[str, Any]]:
    """Filter events list for proof submissions from a specific sub-chain."""
    return [
        event
        for event in events
        if (
            event.get("event") == "proof_submission"
            and event.get("details", {}).get("sub_chain_name") == sub_chain_name
        )
    ]


def _record_proof_on_main_chain(
    chain: "MainChain",
    sub_chain_name: str,
    proof_hash: str,
    sanitized_metadata: dict[str, Any],
    zk_verified: bool,
) -> bool:
    """Record a proof on the Main Chain."""
    proof_id = f"PROOF-{chain.proof_count + 1}"
    current_time = time.time()
    event: dict[str, Any] = {
        "entity_id": sub_chain_name,
        "event": "proof_submission",
        "timestamp": current_time,
        "type": "sub_chain_proof",
        "sub_chain": sub_chain_name,
        "proof_hash": proof_hash,
        "metadata": sanitized_metadata,
        "zk_verified": zk_verified,
        "details": {
            "sub_chain_name": sub_chain_name,
            "proof_hash": proof_hash,
            "proof_id": proof_id,
            "submitted_at": current_time,
            "zk_verified": zk_verified,
        },
    }

    chain.add_event(event)
    chain.proof_count += 1

    chain.latest_proofs[sub_chain_name] = {
        "proof_hash": proof_hash,
        "timestamp": current_time,
        "block_index": chain.get_latest_block().index + 1,
    }

    _update_recent_proofs_on_main_chain(
        chain,
        sub_chain_name,
        proof_hash,
        sanitized_metadata,
        current_time,
    )
    return True


def _update_recent_proofs_on_main_chain(
    chain: "MainChain",
    sub_chain_name: str,
    proof_hash: str,
    sanitized_metadata: dict[str, Any],
    timestamp: float,
) -> None:
    """Update the recent proofs on the Main Chain."""
    recent_proof_entry = {
        "block_index": chain.get_latest_block().index + 1,
        "sub_chain": sub_chain_name,
        "proof_hash": proof_hash,
        "metadata": sanitized_metadata,
        "timestamp": timestamp,
    }
    chain.recent_proofs.append(recent_proof_entry)
    if len(chain.recent_proofs) > 10:
        chain.recent_proofs.pop(0)


def _verify_proof_in_main_chain(chain: "MainChain", proof_hash: str, sub_chain_name: str) -> bool:
    """Verify a proof exists in the Main Chain."""
    for block in chain.chain:
        events = (
            block.to_event_list()
            if hasattr(block, "to_event_list")
            else block.events
        )
        if _find_proof_in_events(events, proof_hash, sub_chain_name):
            return True

    return _find_proof_in_events(chain.pending_events, proof_hash, sub_chain_name)


def _get_proofs_by_sub_chain_from_main_chain(chain: "MainChain", sub_chain_name: str) -> list[dict[str, Any]]:
    """Get all proofs submitted by a specific Sub-Chain from the Main Chain."""
    proofs: list[dict[str, Any]] = []
    for block in chain.chain:
        events = (
            block.to_event_list()
            if hasattr(block, "to_event_list")
            else block.events
        )
        proofs.extend(_filter_proofs_by_sub_chain(events, sub_chain_name))

    proofs.extend(_filter_proofs_by_sub_chain(chain.pending_events, sub_chain_name))
    return proofs


def _get_sub_chain_summary_from_main_chain(chain: "MainChain", sub_chain_name: str) -> dict[str, Any]:
    """Get summary information about a Sub-Chain from the Main Chain."""
    if sub_chain_name not in chain.registered_sub_chains:
        return {}

    proofs = _get_proofs_by_sub_chain_from_main_chain(chain, sub_chain_name)

    return {
        "sub_chain_name": sub_chain_name,
        "registered": True,
        "total_proofs": len(proofs),
        "metadata": chain.sub_chain_metadata.get(sub_chain_name, {}),
        "latest_proof": proofs[-1] if proofs else None,
        "registration_time": chain.sub_chain_metadata.get(sub_chain_name, {}).get(
            "registered_at"
        ),
    }


def _get_main_chain_stats_for_chain(chain: "MainChain") -> dict[str, Any]:
    """Get comprehensive statistics about the Main Chain."""
    base_stats = chain.get_chain_stats()
    proof_events = chain.get_events_by_type("proof_submission")

    return {
        **base_stats,
        "role": "main_chain",
        "registered_sub_chains": len(chain.registered_sub_chains),
        "sub_chains": list(chain.registered_sub_chains),
        "total_proofs": len(proof_events),
        "consensus_type": chain.consensus.name,
        "authorities": chain.consensus.get_validator_count(),
    }


def _get_hierarchical_integrity_report_for_chain(chain: "MainChain") -> dict[str, Any]:
    """Generate an integrity report for the entire hierarchical system."""
    sub_chains: dict[str, Any] = {}
    for sub_chain_name in chain.registered_sub_chains:
        sub_chains[sub_chain_name] = _get_sub_chain_summary_from_main_chain(
            chain,
            sub_chain_name,
        )

    return {
        "main_chain": {
            "name": chain.name,
            "blocks": len(chain.chain),
            "valid": chain.is_chain_valid(),
            "latest_hash": chain.get_latest_block().hash,
        },
        "sub_chains": sub_chains,
        "total_proofs": chain.proof_count,
        "registered_sub_chains": len(chain.registered_sub_chains),
        "system_integrity": "healthy"
        if chain.is_chain_valid()
        else "compromised",
    }


class MainChain(Blockchain):
    """
    Main Chain implementation for the HieraChain Ledger.

    The Main Chain acts as the root authority (like a CEO in an organization) and:
    - Only stores proofs from Sub-Chains, NOT detailed domain data
    - Maintains the integrity of the entire hierarchical system
    - Provides proof verification and chain coordination
    - Uses Proof of Authority consensus suitable for business applications
    """

    def __init__(self, name: str = "MainChain"):
        """
        Initialize the Main Chain.

        Args:
            name: Name identifier for the Main Chain
        """
        super().__init__(name)

        # Dynamic Consensus Loading
        if settings.CONSENSUS_TYPE == "proof_of_federation":
            self.consensus = ProofOfFederation("MainChain_PoF")
        else:
            # Default back to PoA
            self.consensus = ProofOfAuthority("MainChain_PoA")

        self.registered_sub_chains: set[str] = set()
        self.sub_chain_metadata: dict[str, dict[str, Any]] = {}
        self.proof_count: int = 0
        self.latest_proofs: dict[str, dict[str, Any]] = {}
        self.recent_proofs: list[dict[str, Any]] = []

        # ZK Proof Verifier (initialized if ZK proofs are enabled)
        self.zk_verifier: ZKVerifier | None = None
        if settings.ENABLE_ZK_PROOFS:
            self.zk_verifier = ZKVerifier(mode=settings.ZK_MODE)
            logger.info(f"MainChain initialized with ZK Verification in '{settings.ZK_MODE}' mode")

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

    def register_sub_chain(self, sub_chain_name: str, metadata: dict[str, Any] | None = None) -> bool:
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
            logger.warning(f"Rejected proof: SubChain '{sub_chain_name}' not registered")
            return False

        if not isinstance(metadata, dict):
            logger.warning(f"Rejected proof: Invalid metadata type from '{sub_chain_name}'")
            return False

        if not validate_proof_metadata(metadata):
            logger.warning(f"Rejected proof: Invalid metadata from '{sub_chain_name}'")
            return False

        # === ZK PROOF VERIFICATION ===
        zk_verified = self._verify_zk_proof(sub_chain_name, proof_hash, metadata, zk_proof)
        if settings.ENABLE_ZK_PROOFS and zk_proof is not None and not zk_verified:
            return False

        # Sanitize metadata to ensure only summary data
        sanitized_metadata = sanitize_metadata_for_main_chain(metadata)

        # Record proof and update state
        return _record_proof_on_main_chain(self, sub_chain_name, proof_hash, sanitized_metadata, zk_verified)

    def _verify_zk_proof(
        self,
        sub_chain_name: str,
        proof_hash: str,
        metadata: dict[str, Any],
        zk_proof: bytes | None
    ) -> bool:
        """Verify ZK proof if enabled and provided."""
        if not settings.ENABLE_ZK_PROOFS:
            return False

        if self.zk_verifier is None:
            logger.error("ZK Proofs enabled but ZKVerifier not initialized")
            return False

        # Check if ZK proof is required
        if settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN and zk_proof is None:
            logger.warning("Rejected proof: ZK proof required but missing")
            return False

        if zk_proof is None:
            return False

        public_inputs = {
            "old_state_root": metadata.get("previous_merkle_root", ""),
            "new_state_root": metadata.get("latest_merkle_root", proof_hash),
            "block_index": metadata.get("latest_block_index", 0),
            "sub_chain_name": sub_chain_name
        }

        try:
            is_valid = self.zk_verifier.verify(zk_proof, public_inputs)
            if not is_valid:
                logger.error(
                    f"ZK Proof FAILED for '{sub_chain_name}' "
                    f"block {public_inputs['block_index']}"
                )
                return False
            logger.info(
                f"ZK Proof VERIFIED for '{sub_chain_name}' "
                f"block {public_inputs['block_index']}"
            )
            return True
        except ZKVerificationError as e:
            logger.error(f"ZK Verification error: {e}")
            return False

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
        if not self.pending_events:
            return None

        # Create block with pending events
        new_block = self.create_block()

        # Finalize block using PoA consensus
        finalized_block = self.consensus.finalize_block(new_block, "main_chain")

        # Add finalized block to chain
        if self.add_block(finalized_block):
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
        if not self.pending_events:
            return None

        # Create block with pending events
        new_block = self.create_block()

        # Finalize block using PoA consensus
        finalized_block = self.consensus.finalize_block(new_block, "main_chain")

        # Add finalized block to chain
        if self.add_block(finalized_block):
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
