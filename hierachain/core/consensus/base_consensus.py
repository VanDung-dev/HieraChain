"""
Base Consensus mechanism for HieraChain Ledger.

This module defines the abstract base class for consensus mechanisms.
The Ledger supports various consensus algorithms while maintaining
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
    in the HieraChain Ledger. It ensures that consensus algorithms
    work with the event-based model and support the hierarchical structure.
    """

    # Terms that should not appear in non-technical event fields
    FORBIDDEN_TERMS = ["transaction", "mining", "coin", "token", "wallet", "fee"]

    # Fields that are excluded from content validation (hashes, signatures, etc.)
    EXCLUDED_CONTENT_FIELDS = {
        "authority_signature",
        "signature",
        "hash",
        "proof_hash",
        "zk_proof",
        "merkle_root",
        "previous_state",
        "current_state",
        "details",
        "event",
        "timestamp"
    }

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

    def _contains_forbidden_terms(self, value: Any) -> bool:
        """
        Check if a value contains any forbidden cryptocurrency-related terms.

        Args:
            value: The value to check (will be converted to lower-case string)

        Returns:
            True if a forbidden term is found, False otherwise
        """
        value_str = str(value).lower()
        return any(term in value_str for term in self.FORBIDDEN_TERMS)

    def _is_event_structure_valid(self, event: Any) -> bool:
        """Check if basic event structure and required fields are present."""
        if not isinstance(event, dict):
            return False
        return "event" in event and "timestamp" in event

    def _check_content_fields(self, data: dict[str, Any]) -> bool:
        """Validate a dictionary of fields for forbidden content."""
        return not any(
            self._contains_forbidden_terms(value)
            for key, value in data.items()
            if key not in self.EXCLUDED_CONTENT_FIELDS
        )

    def _validate_details_content(self, details: Any) -> bool:
        """Validate the details field content."""
        if isinstance(details, dict):
            return self._check_content_fields(details)
        if details and isinstance(details, str):
            return not self._contains_forbidden_terms(details)
        return True

    def validate_event_for_consensus(self, event: dict[str, Any]) -> bool:
        """
        Validate an event according to consensus-specific rules.

        This method checks for event integrity and ensures it doesn't contain
        disallowed cryptocurrency-related terminology in content fields.
        """
        if isinstance(event, (pa.Table, pa.RecordBatch)):
            return True

        return (
            self._is_event_structure_valid(event) and
            not self._contains_forbidden_terms(event.get("event", "")) and
            self._validate_details_content(event.get("details")) and
            self._check_content_fields(event)
        )

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

    def __str__(self) -> str:
        """String representation of the consensus mechanism."""
        return f"{self.__class__.__name__}(name={self.name})"

    def __repr__(self) -> str:
        """Detailed string representation of the consensus mechanism."""
        return f"{self.__class__.__name__}(name={self.name}, config={self.config})"


def _extract_zk_proof_data(block: Block) -> tuple[str | None, dict[str, Any]]:
    """Extract ZK proof and details from block events."""
    events = block.to_event_list() if hasattr(block, 'to_event_list') else []
    for event in events:
        if event.get("event") == "consensus_finalization":
            details = event.get("details", {})
            return details.get("zk_proof"), details
    return None, {}


def _build_public_inputs(
    block: Block,
    previous_block: Block | None,
    details: dict[str, Any]
) -> dict[str, Any]:
    """Build public inputs for ZK verification."""
    old_state = details.get("previous_state")
    if old_state is None and previous_block:
        old_state = getattr(previous_block, 'merkle_root', None) or "genesis"

    return {
        "old_state_root": old_state or "",
        "new_state_root": (
            details.get("current_state")
            or getattr(block, 'merkle_root', None)
            or block.hash
        ),
        "block_index": block.index
    }


def _verify_block_zk_proof(block: Block, previous_block: Block | None = None) -> bool:
    """
    Verify ZK proof attached to a block's consensus event.

    Returns:
        True if ZK proof is valid or not required, False otherwise
    """
    if not settings.ENABLE_ZK_PROOFS:
        return True

    zk_proof, details = _extract_zk_proof_data(block)

    if zk_proof is None:
        if settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN:
            logger.warning(
                "Block %s: ZK proof required but missing",
                block.index
            )
            return False
        return True

    try:
        verifier = get_zk_verifier()
        public_inputs = _build_public_inputs(
            block, previous_block, details
        )

        if isinstance(zk_proof, str):
            zk_proof = bytes.fromhex(zk_proof)

        return verifier.verify(zk_proof, public_inputs)

    except Exception as e:
        logger.error("ZK verification error in block %s: %s", block.index, e)
        return False
