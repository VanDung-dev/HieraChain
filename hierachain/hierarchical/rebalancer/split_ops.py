"""
Rebalancer split operations — chain splitting, event migration, and targeting strategies.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import TYPE_CHECKING, Any

from hierachain.hierarchical.rebalancer.types import SplitResult, RebalanceStatus, SplitStrategy

if TYPE_CHECKING:
    from hierachain.hierarchical.rebalancer.rebalancer import SubChainRebalancer

logger = logging.getLogger(__name__)


def _get_sub_chain_id(subchain: Any) -> str:
    if hasattr(subchain, "name"):
        return subchain.name
    if hasattr(subchain, "sub_chain_id"):
        return subchain.sub_chain_id
    return f"subchain-{id(subchain)}"


def _get_event_count(subchain: Any) -> int:
    if hasattr(subchain, "get_event_count"):
        return subchain.get_event_count()
    if hasattr(subchain, "blockchain"):
        blocks = subchain.blockchain.get_chain()
        return sum(len(b.events) for b in blocks if hasattr(b, "events"))
    return 0


def _get_block_count(subchain: Any) -> int:
    if hasattr(subchain, "get_block_count"):
        return subchain.get_block_count()
    if hasattr(subchain, "blockchain"):
        return len(subchain.blockchain.get_chain())
    return 0


def _get_pending_events(subchain: Any) -> list[Any]:
    if hasattr(subchain, "get_pending_events"):
        return subchain.get_pending_events()
    return []


def _add_event_to_chain(chain: Any, event: Any) -> bool:
    try:
        if hasattr(chain, "add_event"):
            return chain.add_event(event)
        return True
    except Exception as e:
        logger.error("Failed to add event to chain: %s", e)
        return False


def _get_event_entity_id(event: Any) -> str:
    if isinstance(event, dict):
        return event.get("entity_id", str(id(event)))
    if hasattr(event, "entity_id"):
        return event.entity_id
    return str(id(event))


def _get_event_timestamp(event: Any) -> float:
    if isinstance(event, dict):
        return event.get("timestamp", time.time())
    if hasattr(event, "timestamp"):
        return event.timestamp
    return time.time()


def _mark_chain_as_split(parent: Any, children: list[Any]) -> None:
    if hasattr(parent, "mark_split"):
        child_ids = [_get_sub_chain_id(c) for c in children]
        parent.mark_split(child_ids)


def _split_sub_chain_for_rebalancer(
    rebalancer: SubChainRebalancer, sub_chain: Any
) -> SplitResult:
    start_time = time.time()
    rebalancer.stats["splits_initiated"] += 1
    rebalancer.status = RebalanceStatus.SPLITTING

    parent_id = _get_sub_chain_id(sub_chain)
    child_ids = [f"{parent_id}-a", f"{parent_id}-b"]

    try:
        children = rebalancer.create_child_chains(parent_id, child_ids)
        if not children:
            raise RuntimeError("Failed to create child chains")

        rebalancer.status = RebalanceStatus.MIGRATING
        events_migrated, blocks_migrated = _migrate_state_for_rebalancer(
            rebalancer, sub_chain, children
        )

        rebalancer.stats["events_migrated"] += events_migrated
        rebalancer.stats["splits_completed"] += 1
        rebalancer.status = RebalanceStatus.COMPLETE

        result = SplitResult(
            success=True,
            parent_chain_id=parent_id,
            child_chain_ids=child_ids,
            events_migrated=events_migrated,
            blocks_migrated=blocks_migrated,
            duration_seconds=time.time() - start_time,
        )

        if rebalancer.on_split_complete:
            rebalancer.on_split_complete(result)

        logger.info(
            "Split complete: %s -> %s, %d events migrated",
            parent_id, child_ids, events_migrated
        )

        rebalancer.status = RebalanceStatus.COOLDOWN

        return result

    except Exception as e:
        logger.error("Split failed for %s: %s", parent_id, e)
        rebalancer.stats["splits_failed"] += 1
        rebalancer.status = RebalanceStatus.FAILED
        return SplitResult(
            success=False,
            parent_chain_id=parent_id,
            error_message=str(e),
            duration_seconds=time.time() - start_time,
        )


def _migrate_state_for_rebalancer(
    rebalancer: SubChainRebalancer,
    parent: Any,
    children: list[Any]
) -> tuple[int, int]:
    events_migrated = 0
    blocks_migrated = 0

    if len(children) < 2:
        return 0, 0

    committed_events = _get_committed_block_events(parent)
    for event in committed_events:
        target_idx = _select_target_child_for_rebalancer(
            rebalancer,
            event,
            len(children),
        )
        target = children[target_idx]
        if _add_event_to_chain(target, event):
            events_migrated += 1

    pending_events = _get_pending_events(parent)
    for event in pending_events:
        target_idx = _select_target_child_for_rebalancer(
            rebalancer,
            event,
            len(children),
        )
        target = children[target_idx]
        if _add_event_to_chain(target, event):
            events_migrated += 1

    _mark_chain_as_split(parent, [c for c in children])

    logger.info(
        "Migrated %d events (%d pending + %d committed) from parent %s to %d children",
        events_migrated, len(pending_events), len(committed_events),
        getattr(parent, "name", str(parent)), len(children)
    )

    return events_migrated, blocks_migrated


def _extract_events_from_block(block: Any) -> list[Any]:
    if hasattr(block, "to_event_list"):
        return list(block.to_event_list())
    if hasattr(block, "events"):
        return list(block.events)
    return []


def _get_committed_block_events(subchain: Any) -> list[Any]:
    if not hasattr(subchain, "chain"):
        return []
    events = []
    for block in subchain.chain:
        events.extend(_extract_events_from_block(block))
    return events


def _select_target_child_for_rebalancer(
    rebalancer: SubChainRebalancer,
    event: Any,
    num_children: int,
) -> int:
    if num_children <= 0:
        return 0

    if rebalancer.split_strategy == SplitStrategy.HASH_BASED:
        entity_id = _get_event_entity_id(event)
        hash_val = int(hashlib.sha256(entity_id.encode()).hexdigest()[:8], 16)
        return hash_val % num_children

    if rebalancer.split_strategy == SplitStrategy.TIME_BASED:
        timestamp = _get_event_timestamp(event)
        median_time = time.time() - 30
        return 0 if timestamp < median_time else 1

    if rebalancer.split_strategy == SplitStrategy.ROUND_ROBIN:
        rebalancer.rr_counter = rebalancer.rr_counter + 1
        return rebalancer.rr_counter % num_children

    return 0
