"""
Proof submission and ZK proof functions for Sub-Chain.
"""

import time
import logging
from typing import Any, Callable

from hierachain.config.settings import settings
from hierachain.core.utils import sanitize_metadata_for_main_chain
from hierachain.security.zk_prover import ZKProver

logger = logging.getLogger(__name__)


def _generate_zk_proof(name: str, chain: list[Any], latest_block: Any) -> bytes | None:
    """Generate ZK proof for the latest block transition with retries."""
    if not settings.ENABLE_ZK_PROOFS:
        return None

    old_state_root = _get_old_state_root(chain)
    new_state_root = latest_block.merkle_root or latest_block.hash

    max_attempts = 3
    for attempt in range(max_attempts):
        result = _try_generate_proof(
            name, old_state_root, new_state_root, latest_block, attempt, max_attempts
        )

        if result is not None:
            return result

        _sleep_with_backoff(attempt, max_attempts)

    logger.error(
        "Failed to generate ZK proof for block %d after %d attempts",
        latest_block.index, max_attempts
    )
    return None


def _get_old_state_root(chain: list[Any]) -> str:
    """Get the state root from the previous block."""
    previous_block = chain[-2] if len(chain) > 1 else None
    if previous_block is not None:
        from typing import cast
        return cast(Any, previous_block).merkle_root
    return "genesis"


def _try_generate_proof(
    name: str,
    old_state_root: str,
    new_state_root: str,
    latest_block: Any,
    attempt: int,
    max_attempts: int
) -> bytes | None:
    """Attempt to generate a ZK proof once."""
    try:
        prover = ZKProver(mode=settings.ZK_MODE)
        events = (
            latest_block.to_event_list()
            if hasattr(latest_block, "to_event_list")
            else []
        )
        result = prover.generate_proof(
            old_state_root=old_state_root,
            new_state_root=new_state_root,
            block_index=latest_block.index,
            events=events,
            sub_chain_name=name,
        )

        if result.success:
            logger.info(
                "Generated ZK proof for block %d in %.2fms (Attempt %d/%d)",
                latest_block.index, result.generation_time_ms, attempt + 1, max_attempts
            )
            return result.proof

        logger.warning(
            "ZK proof generation failed for block %d on attempt %d/%d: %s",
            latest_block.index, attempt + 1, max_attempts, result.error,
        )
        return None

    except Exception as e:
        logger.error(
            "ZK proof generation error for block %d on attempt %d/%d: %s",
            latest_block.index, attempt + 1, max_attempts, e,
        )
        return None


def _sleep_with_backoff(attempt: int, max_attempts: int) -> None:
    """Sleep with exponential backoff between retry attempts."""
    if attempt < max_attempts - 1:
        time.sleep(1.0 * (attempt + 1))


def _generate_default_proof_metadata(
    chain: list[Any],
    domain_type: str,
    latest_block_index: int,
    completed_ops: int
) -> dict[str, Any]:
    """Generate default proof metadata for Main Chain submission."""
    recent_events: list[dict[str, Any]] = []
    for block in chain[-5:]:
        events = (
            block.to_event_list()
            if hasattr(block, "to_event_list")
            else block.events
        )
        recent_events.extend(events)

    event_counts: dict[str, int] = {}
    entity_count = set()

    for event in recent_events:
        event_type = event.get("event", "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

        if event.get("entity_id") is not None:
            entity_count.add(event["entity_id"])

    metadata = {
        "domain_type": domain_type,
        "latest_block_index": latest_block_index,
        "total_blocks": len(chain),
        "recent_events": len(recent_events),
        "unique_entities": len(entity_count),
        "completed_operations": completed_ops,
        "event_types": list(event_counts.keys()),
        "proof_timestamp": time.time(),
    }

    return sanitize_metadata_for_main_chain(metadata)


def _submit_proof_for_sub_chain(
    sub_chain: "SubChain",
    main_chain: Any,
    metadata_filter: Callable | None,
) -> bool:
    """Submit a cryptographic proof to the Main Chain."""
    latest_block = sub_chain.get_latest_block()
    logger.debug(
        "SubChain %s submitting proof. "
        "Chain length: %d. Block index: %d",
        sub_chain.name, len(sub_chain.chain), latest_block.index,
    )

    if not sub_chain.chain or len(sub_chain.chain) <= 1:
        logger.debug("SubChain has only genesis block. Aborting proof.")
        return False

    if not latest_block.hash or latest_block.hash == "0" * 64:
        logger.warning(
            "SubChain %s: Cannot submit proof - latest block %d not finalized (hash=%s)",
            sub_chain.name, latest_block.index, latest_block.hash
        )
        return False

    if latest_block.index < 0:
        logger.warning(
            "SubChain %s: Cannot submit proof - latest block has invalid index %d",
            sub_chain.name, latest_block.index
        )
        return False

    metadata = (
        metadata_filter(sub_chain)
        if metadata_filter
        else _generate_default_proof_metadata(
            sub_chain.chain,
            sub_chain.domain_type,
            latest_block.index,
            sub_chain.completed_operations,
        )
    )

    zk_proof = _generate_zk_proof(sub_chain.name, sub_chain.chain, latest_block)
    if zk_proof is None and settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN:
        return False

    success = main_chain.add_proof(
        sub_chain_name=sub_chain.name,
        proof_hash=latest_block.hash,
        metadata=metadata,
        zk_proof=zk_proof,
    )
    logger.debug("MainChain.add_proof returned: %s", success,)

    if success:
        _update_local_state_after_proof(sub_chain, main_chain, latest_block, zk_proof)

    return success


def _update_local_state_after_proof(
    sub_chain: Any,
    main_chain: Any,
    latest_block: Any,
    zk_proof: bytes | None
) -> None:
    """Update local state after successful proof submission."""
    sub_chain.last_proof_submission = time.time()

    proof_event = {
        "entity_id": sub_chain.name,
        "event": "proof_submitted",
        "timestamp": time.time(),
        "details": {
            "main_chain_name": getattr(main_chain, "name", str(main_chain)),
            "proof_hash": latest_block.hash,
            "block_index": latest_block.index,
            "submitted_at": time.time(),
            "zk_proof_included": zk_proof is not None,
        },
    }

    sub_chain.add_event(proof_event)


def _connect_sub_chain_to_main(sub_chain: "SubChain", main_chain: Any) -> bool:
    """Connect a Sub-Chain to the Main Chain."""
    try:
        metadata = {
            "domain_type": sub_chain.domain_type,
            "sub_chain_name": sub_chain.name,
            "connected_at": time.time(),
            "capabilities": ["domain_operations", "proof_submission"],
        }

        if main_chain.register_sub_chain(sub_chain.name, metadata):
            sub_chain.main_chain_connection = main_chain

            connection_event = {
                "entity_id": sub_chain.name,
                "event": "main_chain_connection",
                "timestamp": time.time(),
                "details": {
                    "main_chain_name": getattr(main_chain, "name", str(main_chain)),
                    "connected_at": time.time(),
                    "status": "connected",
                },
            }

            sub_chain.add_event(connection_event)
            return True
    except (AttributeError, TypeError, ValueError):
        return False

    return False
