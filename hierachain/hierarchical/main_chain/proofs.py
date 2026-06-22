"""
Proof helper functions for Main Chain.
"""

import time
import logging
from typing import Any, TYPE_CHECKING

from hierachain.core.block import table_to_list_of_dicts
from hierachain.config.settings import settings
from hierachain.security.verify.zk_verifier import ZKVerificationError

if TYPE_CHECKING:
    from hierachain.hierarchical.main_chain.base import MainChain

logger = logging.getLogger(__name__)


def _is_valid_hash_format(hash_str: str) -> bool:
    """Validate that a string is a proper SHA-256 hex digest (64 hex chars)."""
    if not isinstance(hash_str, str) or len(hash_str) != 64:
        return False
    try:
        int(hash_str, 16)
        return True
    except (ValueError, TypeError):
        return False


def _find_proof_in_events(
    events: list[dict[str, Any]], proof_hash: str, sub_chain_name: str
) -> bool:
    """Check if a proof exists in a list of events."""
    for event in events:
        if (
            event.get("event") == "proof_submission"
            and event.get("details", {}).get("proof_hash") == proof_hash
            and event.get("details", {}).get("sub_chain_name") == sub_chain_name
        ):
            return True
    return False


def _filter_proofs_by_sub_chain(
    events: list[dict[str, Any]], sub_chain_name: str
) -> list[dict[str, Any]]:
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
    with chain.lock:
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

        # Update proof index for O(1) lookup
        if sub_chain_name not in chain.proof_index:
            chain.proof_index[sub_chain_name] = []
        chain.proof_index[sub_chain_name].append(chain.get_latest_block().index + 1)

        _update_recent_proofs_on_main_chain(
            chain, sub_chain_name, proof_hash,
            sanitized_metadata, current_time,
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


def _verify_proof_in_main_chain(
    chain: "MainChain", proof_hash: str, sub_chain_name: str
) -> bool:
    """Verify a proof exists in the Main Chain using the proof index."""
    # Use index to avoid full chain scan
    block_indices = chain.proof_index.get(sub_chain_name, [])
    for idx in block_indices:
        if idx < len(chain.chain):
            block = chain.chain[idx]
            events = (
                block.to_event_list()
                if hasattr(block, "to_event_list")
                else table_to_list_of_dicts(block.events)
            )
            if _find_proof_in_events(events, proof_hash, sub_chain_name):
                return True

    return _find_proof_in_events(chain.pending_events, proof_hash, sub_chain_name)


def _get_proofs_by_sub_chain_from_main_chain(
    chain: "MainChain", sub_chain_name: str
) -> list[dict[str, Any]]:
    """Get all proofs submitted by a specific Sub-Chain using the proof index."""
    proofs: list[dict[str, Any]] = []
    
    # Use index to avoid full chain scan
    block_indices = chain.proof_index.get(sub_chain_name, [])
    for idx in block_indices:
        if idx < len(chain.chain):
            block = chain.chain[idx]
            events = (
                block.to_event_list()
                if hasattr(block, "to_event_list")
                else table_to_list_of_dicts(block.events)
            )
            proofs.extend(_filter_proofs_by_sub_chain(events, sub_chain_name))

    proofs.extend(_filter_proofs_by_sub_chain(chain.pending_events, sub_chain_name))
    return proofs


def _verify_zk_proof_helper(
    zk_verifier: Any,
    sub_chain_name: str,
    proof_hash: str,
    metadata: dict[str, Any],
    zk_proof: bytes | None
) -> bool:
    """Verify ZK proof if enabled and provided."""
    if not settings.ENABLE_ZK_PROOFS:
        return False

    if not settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN:
        logger.warning(
            "ZK Proofs are ENABLED but NOT REQUIRED for MainChain. "
            "SubChain '%s' proof will be accepted without ZK verification. "
            "This may pose a security risk if misconfigured.",
            sub_chain_name
        )

    if zk_verifier is None:
        logger.error("ZK Proofs enabled but ZKVerifier not initialized")
        return False

    # Check if ZK proof is required
    if settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN and zk_proof is None:
        logger.critical("CRITICAL: Rejected proof from '%s'. ZK proof is REQUIRED but missing.", sub_chain_name)
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
        is_valid = zk_verifier.verify(zk_proof, public_inputs)
        if not is_valid:
            logger.error(
                "ZK Proof FAILED for '%s' "
                "block %s",
                sub_chain_name,
                public_inputs["block_index"],
            )
            return False
        logger.info(
            "ZK Proof VERIFIED for '%s' "
            "block %s",
            sub_chain_name,
            public_inputs["block_index"],
        )
        return True
    except ZKVerificationError as e:
        logger.error(
            "ZK Verification error for '%s' "
            "block %s: %s",
            sub_chain_name,
            public_inputs["block_index"],
            e,
        )
        return False
