"""
Entity Tracer for HieraChain Framework.

This module provides comprehensive entity tracing capabilities across
the HieraChain system, allowing tracking of entities
across multiple Sub-Chains while maintaining framework guidelines.
"""

import time
from typing import Any
from collections import defaultdict
from hierachain.hierarchical.hierarchy_manager import HierarchyManager


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
        "interaction_timeline": []
    }


def _get_current_status(events: list[dict[str, Any]]) -> str | None:
    """Get the current status of an entity from its events."""
    # Find the most recent status update
    status_events = [e for e in events if e.get("event") == "status_update"]
    if status_events:
        latest_status_event = max(status_events, key=lambda x: x.get("timestamp", 0))
        return latest_status_event.get("details", {}).get("new_status")

    # If no status updates, check for registration
    registration_events = [e for e in events if e.get("event") == "entity_registration"]
    if registration_events:
        return "registered"

    return None


def _extract_relationships_from_event(
    event: dict[str, Any],
    related_entities: dict[str, list[str]]
) -> None:
    """Extract entity relationships from a single event."""
    details = event.get("details", {})
    event_type = event.get("event")

    # Map event types to relationship categories and detail keys
    rel_map = {
        "resource_assigned": ("shared_resources", "resource_id"),
        "approval": ("approvers", "approver_id"),
        "quality_check": ("inspectors", "inspector_id"),
        "operation_start": ("processors", "processor_id"),
        "operation_complete": ("processors", "processor_id")
    }

    if event_type in rel_map:
        category, detail_key = rel_map[event_type]
        entity_id = details.get(detail_key)
        if entity_id:
            related_entities[category].append(entity_id)


def _filter_and_deduplicate_relationships(
    related_entities: dict[str, list[str]],
    relationship_types: list[str] | None
) -> dict[str, list[str]]:
    """Deduplicate and optionally filter relationship types."""
    processed = {}

    # Deduplicate
    for rel_type, entities in related_entities.items():
        if not relationship_types or rel_type in relationship_types:
            processed[rel_type] = list(set(entities))

    return processed


def _handle_quality_counter(
    details: dict[str, Any],
    counters: dict[str, int]
) -> None:
    """Handle quality check counters."""
    counters["quality_checks"] += 1
    if details.get("check_result") == "passed":
        counters["quality_passed"] += 1


def _handle_approval_counter(
    details: dict[str, Any],
    counters: dict[str, int]
) -> None:
    """Handle approval counters."""
    counters["approvals"] += 1
    if details.get("approval_status") == "approved":
        counters["approvals_granted"] += 1


def _handle_compliance_counter(
    details: dict[str, Any],
    counters: dict[str, int]
) -> None:
    """Handle compliance counters."""
    counters["compliance_checks"] += 1
    if details.get("compliance_status") == "non_compliant":
        counters["compliance_violations"] += 1


def _update_performance_counters(
    event: dict[str, Any],
    counters: dict[str, int]
) -> None:
    """Update performance counters based on event type."""
    event_type = event.get("event")
    details = event.get("details", {})

    if event_type == "operation_start":
        counters["total_operations"] += 1
    elif event_type == "operation_complete":
        counters["completed_operations"] += 1
    elif event_type == "quality_check":
        _handle_quality_counter(details, counters)
    elif event_type == "approval":
        _handle_approval_counter(details, counters)
    elif event_type == "compliance_check":
        _handle_compliance_counter(details, counters)


def _calculate_performance_metrics(c: dict[str, int]) -> dict[str, float]:
    """Calculate rates and ratios from performance counters."""
    return {
        "total_operations": c["total_operations"],
        "completed_operations": c["completed_operations"],
        "completion_rate": c["completed_operations"] / max(c["total_operations"], 1),
        "quality_checks": c["quality_checks"],
        "quality_pass_rate": c["quality_passed"] / max(c["quality_checks"], 1),
        "approvals": c["approvals"],
        "approval_rate": c["approvals_granted"] / max(c["approvals"], 1),
        "compliance_checks": c["compliance_checks"],
        "compliance_violations": c["compliance_violations"],
        "compliance_rate": (
            (c["compliance_checks"] - c["compliance_violations"]) /
            max(c["compliance_checks"], 1)
        )
    }


def _generate_recommendations(
    lifecycle: dict[str, Any],
    performance: dict[str, Any],
    relationships: dict[str, Any]
) -> list[str]:
    """Generate recommendations based on entity analysis."""
    recommendations = []

    perf_metrics = performance.get("performance_metrics", {})

    # Performance recommendations
    if perf_metrics.get("completion_rate", 0) < 0.8:
        recommendations.append(
            "Incomplete operations detected - completion rate is below 80%"
        )

    if perf_metrics.get("quality_pass_rate", 0) < 0.9:
        recommendations.append(
            "Quality checks are failing frequently - review quality processes"
        )

    if perf_metrics.get("compliance_violations", 0) > 0:
        recommendations.append(
            "Compliance violations detected - immediate attention required"
        )

    # Activity recommendations
    activity = performance.get("activity_summary", {})
    if activity.get("last_activity", 0) < time.time() - 86400:  # 24 hours
        recommendations.append(
            "Entity has been inactive for over 24 hours - check if this is expected"
        )

    # Lifecycle recommendations
    if len(lifecycle.get("lifecycle_stages", [])) < 3:
        recommendations.append(
            "Entity appears to be in early lifecycle stages - monitor progress"
        )

    # Relationship recommendations
    total_relationships = sum(len(entities) for entities in relationships.values())
    if total_relationships == 0:
        recommendations.append(
            "Entity has no identified relationships - verify if this is expected"
        )
    elif total_relationships > 10:
        recommendations.append(
            "Entity has many relationships - consider reviewing for complexity "
            "management"
        )

    return recommendations


class EntityTracer:
    """
    Entity tracing utility for the HieraChain framework.

    This class provides comprehensive entity tracking capabilities:
    - Trace entities across multiple Sub-Chains
    - Generate entity lifecycle reports
    - Analyze cross-chain entity interactions
    - Provide entity performance metrics
    - Maintain entity relationship mapping
    """

    def __init__(self, hierarchy_manager: HierarchyManager):
        """
        Initialize the Entity Tracer.

        Args:
            hierarchy_manager: HierarchyManager instance to trace entities across
        """
        self.hierarchy_manager = hierarchy_manager
        self.entity_cache: dict[str, dict[str, Any]] = {}
        self.relationship_cache: dict[str, set[str]] = defaultdict(set)
        self.last_cache_update = 0.0
        self.cache_ttl = 300.0  # 5 minutes cache TTL

    def trace_entity(
        self,
        entity_id: str,
        include_details: bool = True
    ) -> dict[str, Any]:
        """
        Trace an entity across all Sub-Chains in the hierarchy.

        Args:
            entity_id: Entity identifier to trace
            include_details: Whether to include detailed event information

        Returns:
            Comprehensive entity trace information
        """
        # Get entity trace from hierarchy manager
        entity_trace = self.hierarchy_manager.trace_entity_across_chains(entity_id)

        if not entity_trace:
            return {
                "entity_id": entity_id,
                "found": False,
                "chains": [],
                "total_events": 0,
                "first_seen": None,
                "last_seen": None
            }

        # Analyze the trace
        total_events = 0
        first_seen = float('inf')
        last_seen = 0.0
        chain_summaries = {}

        for chain_name, events in entity_trace.items():
            total_events += len(events)

            if events:
                chain_first = min(
                    event.get("timestamp", 0) for event in events
                )
                chain_last = max(
                    event.get("timestamp", 0) for event in events
                )

                first_seen = min(first_seen, chain_first)
                last_seen = max(last_seen, chain_last)

                # Create chain summary
                event_types = list(set(event.get("event") for event in events))
                chain_summaries[chain_name] = {
                    "total_events": len(events),
                    "event_types": event_types,
                    "first_event": chain_first,
                    "last_event": chain_last,
                    "events": events if include_details else []
                }

        return {
            "entity_id": entity_id,
            "found": True,
            "chains": list(entity_trace.keys()),
            "total_events": total_events,
            "first_seen": first_seen if first_seen != float('inf') else None,
            "last_seen": last_seen if last_seen > 0 else None,
            "chain_details": chain_summaries,
            "traced_at": time.time()
        }

    def get_entity_lifecycle(
        self,
        entity_id: str
    ) -> dict[str, Any]:
        """
        Get comprehensive lifecycle information for an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            Entity lifecycle information
        """
        trace = self.trace_entity(entity_id, include_details=True)

        if not trace["found"]:
            return trace

        # Analyze lifecycle stages
        all_events = []
        for chain_details in trace["chain_details"].values():
            all_events.extend(chain_details["events"])

        # Sort events by timestamp
        all_events.sort(key=lambda x: x.get("timestamp", 0))

        # Identify lifecycle stages
        lifecycle_stages = _identify_lifecycle_stages(all_events)

        # Calculate lifecycle metrics
        duration = (
            trace["last_seen"] - trace["first_seen"]
            if trace["first_seen"] and trace["last_seen"] else 0
        )

        # Analyze status transitions
        status_transitions = _analyze_status_transitions(all_events)

        # Identify cross-chain interactions
        cross_chain_interactions = _analyze_cross_chain_interactions(
            trace["chain_details"]
        )

        return {
            **trace,
            "lifecycle_stages": lifecycle_stages,
            "lifecycle_duration": duration,
            "status_transitions": status_transitions,
            "cross_chain_interactions": cross_chain_interactions,
            "current_status": _get_current_status(all_events),
            "active_chains": len(
                [chain for chain, details in trace["chain_details"].items()
                 if details["last_event"] > time.time() - 86400]
            )  # Active in last 24h
        }

    def find_related_entities(
        self,
        entity_id: str,
        relationship_types: list[str] | None = None
    ) -> dict[str, list[str]]:
        """
        Find entities related to the given entity.

        Args:
            entity_id: Entity identifier
            relationship_types: Types of relationships to look for

        Returns:
            Dictionary mapping relationship types to lists of related entity IDs
        """
        related_entities = defaultdict(list)
        trace = self.trace_entity(entity_id, include_details=True)

        if not trace["found"]:
            return {}

        for chain_details in trace["chain_details"].values():
            for event in chain_details["events"]:
                _extract_relationships_from_event(event, related_entities)

        return _filter_and_deduplicate_relationships(
            related_entities, relationship_types
        )

    def get_entity_performance_summary(self, entity_id: str) -> dict[str, Any]:
        """
        Get performance summary for an entity across all chains.

        Args:
            entity_id: Entity identifier

        Returns:
            Performance summary
        """
        trace = self.trace_entity(entity_id, include_details=True)

        if not trace["found"]:
            return {"entity_id": entity_id, "found": False}

        counters = {
            "total_operations": 0, "completed_operations": 0,
            "quality_checks": 0, "quality_passed": 0,
            "approvals": 0, "approvals_granted": 0,
            "compliance_checks": 0, "compliance_violations": 0
        }

        for chain_details in trace["chain_details"].values():
            for event in chain_details["events"]:
                _update_performance_counters(event, counters)

        duration = (
            trace["last_seen"] - trace["first_seen"]
            if trace["first_seen"] and trace["last_seen"] else 0
        )

        return {
            "entity_id": entity_id,
            "found": True,
            "performance_metrics": _calculate_performance_metrics(counters),
            "activity_summary": {
                "total_events": trace["total_events"],
                "active_chains": len(trace["chains"]),
                "lifecycle_duration": duration,
                "last_activity": trace["last_seen"]
            }
        }

    def generate_entity_report(self, entity_id: str) -> dict[str, Any]:
        """
        Generate a comprehensive report for an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            Comprehensive entity report
        """
        # Get all entity information
        lifecycle = self.get_entity_lifecycle(entity_id)
        performance = self.get_entity_performance_summary(entity_id)
        relationships = self.find_related_entities(entity_id)

        if not lifecycle["found"]:
            return {
                "entity_id": entity_id,
                "found": False,
                "report_generated_at": time.time()
            }

        return {
            "entity_id": entity_id,
            "found": True,
            "report_generated_at": time.time(),
            "lifecycle_information": lifecycle,
            "performance_metrics": performance["performance_metrics"],
            "activity_summary": performance["activity_summary"],
            "relationships": relationships,
            "recommendations": _generate_recommendations(
                lifecycle, performance, relationships
            )
        }

    def trace_entity_in_chain(
        self,
        entity_id: str,
        sub_chain: str
    ) -> dict[str, Any]:
        """
        Trace an entity through a specific sub-chain.

        Args:
            entity_id: Entity identifier to trace
            sub_chain: Name of the sub-chain to trace the entity in

        Returns:
            Entity events and information in the specified sub-chain
        """
        # Get sub-chain from hierarchy manager
        chain = self.hierarchy_manager.get_sub_chain(sub_chain)
        if not chain:
            return {
                "entity_id": entity_id,
                "chain": sub_chain,
                "found": False,
                "events": [],
                "error": f"Sub-chain '{sub_chain}' not found"
            }

        # Use get_entity_history method to get events for this entity
        events = chain.get_entity_history(entity_id)

        return {
            "entity_id": entity_id,
            "chain": sub_chain,
            "found": len(events) > 0,
            "events": events,
            "total_events": len(events)
        }

    def trace_entity_across_chains(
        self,
        entity_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Trace an entity across all sub-chains.

        Args:
            entity_id: Entity identifier to trace across all chains

        Returns:
            Dictionary mapping chain names to lists of entity events
        """
        result = {}

        # Trace entity in all sub-chains
        for name, chain in self.hierarchy_manager.sub_chains.items():
            events = chain.get_entity_history(entity_id)
            if events:
                result[name] = events

        return result

    def __str__(self) -> str:
        """String representation of the Entity Tracer."""
        return (
            f"EntityTracer(hierarchy_manager={self.hierarchy_manager.main_chain.name})"
        )

    def __repr__(self) -> str:
        """Detailed string representation of the Entity Tracer."""
        return (
            f"EntityTracer(main_chain={self.hierarchy_manager.main_chain.name}, "
            f"sub_chains={len(self.hierarchy_manager.sub_chains)}, "
            f"cache_entries={len(self.entity_cache)})"
        )
