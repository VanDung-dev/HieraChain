"""
Proof helper functions for Main Chain.
"""

import logging
import time
from typing import Any

from hierachain.config.settings import settings
from hierachain.consensus.ordering.storage import _block_from_dict
from hierachain.security.verify.zk_verifier import ZKVerificationError

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
        details = event.get("details")
        if (
            event.get("event") == "proof_submission"
            and isinstance(details, dict)
            and details.get("proof_hash") == proof_hash
            and details.get("sub_chain_name") == sub_chain_name
        ):
            return True
    return False


def _proof_already_recorded(
    chain: Any, sub_chain_name: str, proof_hash: str
) -> bool:
    """Find an existing pending or recorded proof while the MainChain is locked."""
    if _find_proof_in_events(
        getattr(chain, "pending_events", []), proof_hash, sub_chain_name
    ):
        return True
    for block in chain.chain:
        events = (
            block.to_event_list()
            if callable(getattr(block, "to_event_list", None))
            else getattr(block, "events", [])
        )
        if _find_proof_in_events(events, proof_hash, sub_chain_name):
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
    chain: Any,
    sub_chain_name: str,
    proof_hash: str,
    sanitized_metadata: dict[str, Any],
    zk_verified: bool,
    zk_proof: bytes | None,
) -> bool:
    """Record a proof on the Main Chain."""
    with chain.lock:
        if _proof_already_recorded(chain, sub_chain_name, proof_hash):
            return True
        proof_id = f"PROOF-{chain.proof_sequence + 1}"
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
            "zk_proof": zk_proof.hex() if zk_proof is not None else None,
            "details": {
                "sub_chain_name": sub_chain_name,
                "proof_hash": proof_hash,
                "proof_id": proof_id,
                "submitted_at": current_time,
                "zk_verified": zk_verified,
            },
        }

        chain.add_event(event)
        chain.proof_sequence += 1
        return True


def _refresh_durable_proofs(chain: Any) -> None:
    """Build public proof counters and indexes from verified stored blocks."""
    index: dict[str, list[int]] = {}
    latest: dict[str, dict[str, Any]] = {}
    recent: list[dict[str, Any]] = []
    for block in chain.chain:
        for event in _durable_block_events(chain, block, strict=True):
            if event.get("event") != "proof_submission":
                continue
            details = event.get("details", {})
            sub_name = details.get("sub_chain_name")
            proof_hash = details.get("proof_hash")
            if not isinstance(sub_name, str) or not isinstance(proof_hash, str):
                raise ValueError("Invalid durable MainChain proof")
            block_indices = index.setdefault(sub_name, [])
            if not block_indices or block_indices[-1] != block.index:
                block_indices.append(block.index)
            latest[sub_name] = {
                "proof_hash": proof_hash,
                "timestamp": event["timestamp"],
                "block_index": block.index,
                "latest_block_index": (
                    event.get("metadata", {}).get("latest_block_index")
                    if isinstance(event.get("metadata"), dict)
                    else None
                ),
            }
            recent.append({
                "block_index": block.index,
                "sub_chain": sub_name,
                "proof_hash": proof_hash,
                "metadata": event.get("metadata", {}),
                "timestamp": event["timestamp"],
            })
    chain.proof_count = len(recent)
    chain.proof_index = index
    chain.latest_proofs = latest
    chain.recent_proofs = recent[-10:]


def _verify_proof_in_main_chain(
    chain: Any, proof_hash: str, sub_chain_name: str
) -> bool:
    """Verify a proof exists in the Main Chain using the proof index."""
    # Use index to avoid full chain scan
    block_indices = chain.proof_index.get(sub_chain_name, [])
    for idx in block_indices:
        if idx < len(chain.chain):
            events = _durable_block_events(chain, chain.chain[idx])
            if _find_proof_in_events(events, proof_hash, sub_chain_name):
                return True

    # Fallback to chain scan in case proof was minted into an unindexed block
    for block in chain.chain:
        events = _durable_block_events(chain, block)
        if _find_proof_in_events(events, proof_hash, sub_chain_name):
            return True

    return False


def _get_proofs_by_sub_chain_from_main_chain(
    chain: Any, sub_chain_name: str
) -> list[dict[str, Any]]:
    """Get all proofs submitted by a specific Sub-Chain using the proof index."""
    proofs: list[dict[str, Any]] = []
    
    # Use index to avoid full chain scan
    block_indices = chain.proof_index.get(sub_chain_name, [])
    for idx in block_indices:
        if idx < len(chain.chain):
            events = _durable_block_events(chain, chain.chain[idx])
            proofs.extend(_filter_proofs_by_sub_chain(events, sub_chain_name))

    return proofs


def _durable_block_events(
    chain: Any, block: Any, *, strict: bool = False
) -> list[dict[str, Any]]:
    """Read only signed block events confirmed in durable storage."""
    storage = getattr(chain, "proof_storage", None)
    if not callable(getattr(storage, "get_block_by_index", None)):
        if strict:
            raise RuntimeError("Durable MainChain storage is unavailable")
        return []
    try:
        saved = storage.get_block_by_index(block.index, chain.name)
        if not isinstance(saved, dict) or saved.get("hash") != block.hash:
            if strict:
                raise RuntimeError(f"MainChain block {block.index} is missing or inconsistent")
            return []
        verified = _block_from_dict(saved, chain.trusted_public_keys)
        return verified.to_event_list()
    except Exception:
        if strict:
            raise
        logger.exception("Could not read durable MainChain block %s", block.index)
        return []


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
