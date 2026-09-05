"""
Domain statistics functions for Sub-Chain.
"""

from typing import Any


def _get_domain_stats_summary(
    chain: list[Any],
    domain_type: str,
    completed_ops: int,
    sub_chain: Any | None = None,
) -> dict[str, Any]:
    """Calculate domain-specific statistics summary.

    Uses pre-aggregated counters from the SubChain object when available
    (O(1)) instead of scanning the entire chain (O(N*E)).
    """
    if (
        sub_chain is not None 
        and hasattr(sub_chain, "entity_event_index") 
        and hasattr(sub_chain, "event_type_counts")
    ):
        return {
            "domain_type": domain_type,
            "unique_entities": len(sub_chain.entity_event_index),
            "completed_operations": completed_ops,
            "operation_types": dict(sub_chain.event_type_counts),
        }

    all_events: list[dict[str, Any]] = []
    for block in chain:
        events = (
            block.to_event_list()
            if hasattr(block, "to_event_list")
            else block.events
        )
        all_events.extend(events)

    unique_entities = set()
    operation_types: dict[str, int] = {}

    for event in all_events:
        if event.get("entity_id") is not None:
            unique_entities.add(event["entity_id"])
        event_type = event.get("event", "unknown")
        operation_types[event_type] = operation_types.get(event_type, 0) + 1

    return {
        "domain_type": domain_type,
        "unique_entities": len(unique_entities),
        "completed_operations": completed_ops,
        "operation_types": operation_types,
    }
