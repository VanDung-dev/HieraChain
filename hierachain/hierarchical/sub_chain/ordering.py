"""
Ordering service rehydration and sync functions for Sub-Chain.
"""

import logging
from queue import Empty
from typing import Any

from hierachain.core.blockchain import Blockchain

logger = logging.getLogger(__name__)


def _check_divergence_and_rehydrate(
    sub_chain: Any, latest_local: Any, latest_db: Any
) -> bool:
    """Check for state divergence between local and database. Returns True if rehydrate is needed."""
    if latest_local.index > latest_db.index:
        local_hash = latest_local.hash
        db_hash = latest_db.hash
        if local_hash != db_hash:
            logger.warning(
                "Chain %s has divergent state! Local hash: %s, DB hash: %s. Will rehydrate.",
                sub_chain.name, local_hash[:16] if local_hash else "None", db_hash[:16] if db_hash else "None"
            )
            return True
        logger.info(
            "Chain %s already up to date with more blocks. Local index: %d, DB index: %d",
            sub_chain.name, latest_local.index, latest_db.index,
        )
        return False

    if latest_local.index == latest_db.index:
        local_hash = latest_local.hash
        db_hash = latest_db.hash
        if local_hash == db_hash:
            logger.info(
                "Chain %s already up to date. Local index: %d, hash: %s",
                sub_chain.name, latest_local.index, local_hash[:16] if local_hash else "None",
            )
            return False
        logger.warning(
            "Chain %s has divergent block at index %d! Local hash: %s, DB hash: %s. Rehydrating.",
            sub_chain.name, latest_local.index,
            local_hash[:16] if local_hash else "None",
            db_hash[:16] if db_hash else "None"
        )
        return True

    return True


def _apply_rehydrated_blocks(sub_chain: Any, all_blocks: list) -> None:
    """Refresh the entire local chain from the reloaded block list."""
    with sub_chain.lock:
        sub_chain.chain.clear()
        sub_chain.world_state.clear()
        for block in all_blocks:
            sub_chain.chain.append(block)
            sub_chain.world_state.apply_block(block)
        Blockchain._rebuild_event_indexes(sub_chain)

    if not sub_chain.is_chain_valid():
        raise ValueError(
            f"Chain {sub_chain.name} failed integrity validation after rehydration"
        )


def _rehydrate_chain_from_ordering_service(
    sub_chain: Any, _latest_block_os: Any
) -> None:
    """Rehydrate the local chain from the Ordering Service."""
    all_blocks = sub_chain.ordering_service.take_bootstrap_blocks()
    if all_blocks is None:
        all_blocks = sub_chain.ordering_service.storage_handler.get_blocks_from_db(start_index=0)

    if not all_blocks:
        return

    latest_local = sub_chain.get_latest_block()
    latest_db = all_blocks[-1]

    should_rehydrate = _check_divergence_and_rehydrate(sub_chain, latest_local, latest_db)
    if not should_rehydrate:
        return

    _apply_rehydrated_blocks(sub_chain, all_blocks)

    logger.info(
        "Rehydrated %d blocks from Ordering Service. Latest index: %d",
        len(all_blocks), all_blocks[-1].index if all_blocks else 0,
    )


def _sync_chain_for_sub_chain(sub_chain: Any) -> None:
    """Synchronize local chain with Ordering Service (Rehydration)."""
    _rehydrate_chain_from_ordering_service(sub_chain, None)
    _discard_rehydrated_blocks_from_queue(sub_chain)


def _discard_rehydrated_blocks_from_queue(sub_chain: Any) -> None:
    """Drop queued blocks already present in the rehydrated chain."""
    # Called from SubChain.__init__ before registration or consumer startup, so
    # no caller can submit new events while this startup queue is reconciled.
    queue = sub_chain.ordering_service.commit_queue
    rehydrated_hashes = {block.index: block.hash for block in sub_chain.chain}
    pending_blocks = []
    conflicting_indexes = []

    while True:
        try:
            block = queue.get_nowait()
        except Empty:
            break

        queue.task_done()
        if block.index not in rehydrated_hashes:
            pending_blocks.append(block)
        elif block.hash != rehydrated_hashes[block.index]:
            pending_blocks.append(block)
            conflicting_indexes.append(block.index)

    for block in pending_blocks:
        queue.put(block)

    if conflicting_indexes:
        raise ValueError(
            "Queued ordering blocks conflict with rehydrated blocks: "
            f"{conflicting_indexes}"
        )
