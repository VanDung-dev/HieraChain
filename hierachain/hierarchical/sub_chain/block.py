"""
Block processing functions for Sub-Chain.
"""

import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _process_and_finalize_single_block(sub_chain: Any, block: Any) -> bool:
    """Process and finalize a single block."""
    with sub_chain.block_processing_lock:
        latest_block = sub_chain.get_latest_block()

        block.index = latest_block.index + 1
        block.previous_hash = latest_block.hash
        block.hash = block.calculate_hash()
        finalized_block = sub_chain.consensus.finalize_block(block, sub_chain.name)

        try:
            sub_chain.ordering_service.storage_handler.save_block(
                finalized_block, sub_chain.name
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Failed to persist finalized block %d: %s", finalized_block.index, e
            )

        if sub_chain.add_block(finalized_block):
            sub_chain.world_state.apply_block(finalized_block)
            sub_chain.auto_submit_proof_if_needed()
            return True

    logger.error("Failed to add ordered block %d", block.index)
    return False


def _finalize_sub_chain_block_for_chain(sub_chain: Any) -> dict[str, Any] | None:
    """Finalize and return a block for the Main Chain."""
    new_blocks: list[Any] = []

    while True:
        block = sub_chain.ordering_service.get_next_block()
        if not block:
            logger.debug(
                "No block from get_next_block. Queue %d empty.",
                id(sub_chain.ordering_service.commit_queue),
            )
            break

        logger.debug(
            f"Got block {block.index} from ordering service. "
            f"Queue {id(sub_chain.ordering_service.commit_queue)}"
        )

        if _process_and_finalize_single_block(sub_chain, block):
            new_blocks.append(block)

    if not new_blocks:
        return None

    last_block = new_blocks[-1]
    return {
        "block_index": last_block.index,
        "block_hash": last_block.hash,
        "events_count": len(last_block.events),
        "finalized_at": time.time(),
        "domain_type": sub_chain.domain_type,
    }


def _flush_pending_and_finalize_for_sub_chain(
    sub_chain: Any, timeout: float
) -> dict[str, Any] | None:
    """Flush pending events and finalize the block."""
    logger.debug("flush_pending_and_finalize for %s", sub_chain.name)
    start_time = time.time()

    while not sub_chain.ordering_service.event_pool.empty():
        if time.time() - start_time > timeout:
            break

    initial_len = len(sub_chain.chain)

    _force_block_creation(sub_chain.ordering_service, timeout)

    result = _finalize_sub_chain_block_for_chain(sub_chain)
    if result:
        return result

    if _wait_for_growth(initial_len, sub_chain.chain, timeout):
        last_block = sub_chain.chain[-1]
        return {
            "block_index": last_block.index,
            "block_hash": last_block.hash,
            "events_count": len(last_block.events),
            "finalized_at": time.time(),
            "domain_type": sub_chain.domain_type,
        }
    return None


def _consumer_loop(sub_chain: Any) -> None:
    """Background loop to continuously pull and finalize blocks."""
    while sub_chain.running and not sub_chain.is_shutting_down:
        try:
            sub_chain.finalize_sub_chain_block()
            time.sleep(0.5)
        except Exception as e:
            logger.error("Error in block consumer loop: %s", e)
            time.sleep(1.0)


def _force_block_creation(ordering_service: Any, timeout: float) -> None:
    """Force the ordering service to create a block from pending events."""
    try:
        ordering_service.force_block_creation(timeout=timeout)
    except Exception as e:
        logger.error("Error forcing block creation: %s", e)


def _wait_for_growth(initial_len: int, chain: list[Any], timeout: float) -> bool:
    """Wait for the chain length to increase."""
    wait_start = time.time()
    while len(chain) == initial_len:
        if time.time() - wait_start > timeout:
            logger.warning("Timeout waiting for block to appear in chain")
            return False
        time.sleep(0.1)
    return True
