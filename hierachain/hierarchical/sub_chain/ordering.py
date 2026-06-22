"""
Ordering service rehydration and sync functions for Sub-Chain.
"""

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hierachain.hierarchical.sub_chain.base import SubChain

logger = logging.getLogger(__name__)


def _check_divergence_and_rehydrate(
    sub_chain: "SubChain", latest_local: Any, latest_db: Any
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


def _apply_rehydrated_blocks(sub_chain: "SubChain", all_blocks: list) -> None:
    """Refresh the entire local chain from the reloaded block list."""
    with sub_chain.lock:
        temp_entity_index = dict(sub_chain.entity_event_index)

        sub_chain.chain.clear()
        sub_chain.total_events = 0
        sub_chain.event_type_counts.clear()
        sub_chain.entity_event_index.clear()

        sub_chain.world_state.clear()
        for block in all_blocks:
            sub_chain.chain.append(block)
            sub_chain.world_state.apply_block(block)
            _update_event_statistics(sub_chain, block)

        for entity_id, events in temp_entity_index.items():
            if entity_id not in sub_chain.entity_event_index:
                sub_chain.entity_event_index[entity_id] = events

        sub_chain.ordering_service.block_history = list(sub_chain.chain)
        sub_chain.ordering_service.blocks_created = all_blocks[-1].index + 1

    if not sub_chain.is_chain_valid():
        logger.warning(
            "Chain %s integrity check detected inconsistencies after rehydration. "
            "This may indicate pending blocks in consumer thread. Will sync on next cycle.",
            sub_chain.name
        )


def _rehydrate_chain_from_ordering_service(
    sub_chain: "SubChain", _latest_block_os: Any
) -> None:
    """Rehydrate the local chain from the Ordering Service."""
    all_blocks = (
        sub_chain.ordering_service.storage_handler.get_blocks_from_db(start_index=0)
    )

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


def _sync_chain_for_sub_chain(sub_chain: "SubChain") -> None:
    """Synchronize local chain with Ordering Service (Rehydration)."""
    try:
        latest_block_os = sub_chain.ordering_service.get_latest_block()
        _rehydrate_chain_from_ordering_service(sub_chain, latest_block_os)
        _reset_ordering_service_state(sub_chain)
    except Exception as e:
        logger.error("Sync failed: %s", e)


def _update_event_statistics(sub_chain: "SubChain", block: Any) -> None:
    """Update event statistics for a block during rehydration."""
    events = (
        block.to_event_list()
        if hasattr(block, "to_event_list")
        else block.events
    )
    sub_chain.total_events += len(events)

    for event in events:
        etype = event.get("event", "unknown")
        sub_chain.event_type_counts[etype] = (
            sub_chain.event_type_counts.get(etype, 0) + 1
        )

        entity_id = event.get("entity_id")
        if entity_id:
            if entity_id not in sub_chain.entity_event_index:
                sub_chain.entity_event_index[entity_id] = []
            sub_chain.entity_event_index[entity_id].append({
                "block_index": block.index,
                "event": event,
            })


def _reset_ordering_service_state(sub_chain: "SubChain") -> None:
    """Reset the Ordering Service state."""
    latest_local = sub_chain.get_latest_block()
    sub_chain.ordering_service.block_history = list(sub_chain.chain)
    sub_chain.ordering_service.blocks_created = latest_local.index + 1
    logger.info(
        "Reset ordering service state: blocks_created = %d",
        sub_chain.ordering_service.blocks_created,
    )
