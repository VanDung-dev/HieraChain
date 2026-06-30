"""
Entity lifecycle stage and transition tracking helpers.
"""

from typing import Any


def _finalize_stage(
    current_stage: dict[str, Any] | None,
    stages: list[dict[str, Any]],
    timestamp: float
) -> None:
    """Finalize the current stage by setting its end time."""
    if current_stage and current_stage.get("stage"):
        current_stage["ended_at"] = timestamp
        stages.append(current_stage)


def _handle_op_start(
    current_stage: dict[str, Any] | None,
    stages: list[dict[str, Any]],
    timestamp: float
) -> dict[str, Any] | None:
    """Handle operation start event."""
    if current_stage and current_stage["stage"] != "in_progress":
        _finalize_stage(current_stage, stages, timestamp)
        return {"stage": "in_progress", "started_at": timestamp}
    return current_stage


def _handle_op_complete(
    current_stage: dict[str, Any] | None,
    stages: list[dict[str, Any]],
    timestamp: float
) -> dict[str, Any] | None:
    """Handle operation complete event."""
    if current_stage and current_stage["stage"] == "in_progress":
        _finalize_stage(current_stage, stages, timestamp)
        return {"stage": "completed", "started_at": timestamp}
    return current_stage


def _handle_quality_stage(
    details: dict[str, Any],
    current_stage: dict[str, Any] | None,
    stages: list[dict[str, Any]],
    timestamp: float
) -> dict[str, Any] | None:
    """Handle quality check pass event."""
    if details.get("check_result") == "passed":
        if current_stage and current_stage["stage"] != "quality_approved":
            _finalize_stage(current_stage, stages, timestamp)
            return {"stage": "quality_approved", "started_at": timestamp}
    return current_stage


def _handle_approval_stage(
    details: dict[str, Any],
    current_stage: dict[str, Any] | None,
    stages: list[dict[str, Any]],
    timestamp: float
) -> dict[str, Any] | None:
    """Handle approval granted event."""
    if details.get("approval_status") == "approved":
        if current_stage and current_stage["stage"] != "approved":
            _finalize_stage(current_stage, stages, timestamp)
            return {"stage": "approved", "started_at": timestamp}
    return current_stage


def _process_lifecycle_event(
    event_type: str,
    timestamp: float,
    details: dict[str, Any],
    current_stage: dict[str, Any] | None,
    stages: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Process a single lifecycle event and return the new current stage."""
    if event_type == "entity_registration":
        return {"stage": "registered", "started_at": timestamp}

    if event_type == "operation_start":
        return _handle_op_start(current_stage, stages, timestamp)

    if event_type == "operation_complete":
        return _handle_op_complete(current_stage, stages, timestamp)

    if event_type == "quality_check":
        return _handle_quality_stage(details, current_stage, stages, timestamp)

    if event_type == "approval":
        return _handle_approval_stage(details, current_stage, stages, timestamp)

    return current_stage


def _identify_lifecycle_stages(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify lifecycle stages from events."""
    stages: list[dict[str, Any]] = []
    current_stage: dict[str, Any] | None = None

    for event in events:
        current_stage = _process_lifecycle_event(
            event.get("event", ""),
            event.get("timestamp", 0),
            event.get("details", {}),
            current_stage,
            stages
        )

    # Add final stage if exists
    if current_stage and current_stage.get("stage"):
        stages.append(current_stage)

    return stages


def _analyze_status_transitions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Analyze status transitions from events."""
    transitions = []

    for event in events:
        if event.get("event") == "status_update":
            details = event.get("details", {})
            transitions.append({
                "timestamp": event.get("timestamp"),
                "from_status": details.get("old_status"),
                "to_status": details.get("new_status"),
                "reason": details.get("reason")
            })

    return transitions


def _identify_chain_transitions(
    sorted_chains: list[tuple[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Identify transitions between chains."""
    transitions = []
    for i in range(len(sorted_chains) - 1):
        current_chain, current_details = sorted_chains[i]
        next_chain, next_details = sorted_chains[i + 1]

        # Check if there's a transition (time gap)
        if next_details["first_event"] > current_details["last_event"]:
            transitions.append({
                "from_chain": current_chain,
                "to_chain": next_chain,
                "transition_time": (
                    next_details["first_event"] - current_details["last_event"]
                )
            })
    return transitions


def _identify_concurrent_chains(
    sorted_chains: list[tuple[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Identify chains that were used concurrently."""
    concurrent = []
    for i, (chain1, details1) in enumerate(sorted_chains):
        for _, (chain2, details2) in enumerate(sorted_chains[i + 1:]):
            # Check for overlap
            if (details1["first_event"] <= details2["last_event"] and
                    details2["first_event"] <= details1["last_event"]):
                concurrent.append({
                    "chain1": chain1,
                    "chain2": chain2,
                    "overlap_start": max(
                        details1["first_event"], details2["first_event"]
                    ),
                    "overlap_end": min(
                        details1["last_event"], details2["last_event"]
                    )
                })
    return concurrent


def _analyze_cross_chain_interactions(
    chain_details: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Analyze cross-chain interactions for an entity."""
    # Sort chains by first event timestamp
    sorted_chains = sorted(
        chain_details.items(),
        key=lambda x: x[1].get("first_event", 0)
    )

    return {
        "total_chains": len(chain_details),
        "chain_transitions": _identify_chain_transitions(sorted_chains),
        "concurrent_chains": _identify_concurrent_chains(sorted_chains),
    }
