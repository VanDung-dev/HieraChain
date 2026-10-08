"""Regression coverage for public WorldState snapshots."""

from typing import Any

from hierachain.state.world_state import WorldState


class _Block:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    def to_event_list(self) -> list[dict[str, Any]]:
        return self.events


def test_getters_and_input_events_cannot_mutate_world_state() -> None:
    details = {"nested": {"tags": ["original"]}}
    state = WorldState()
    state.apply_block(_Block([{
        "entity_id": "entity-1",
        "event": "created",
        "timestamp": 1.0,
        "details": details,
    }]))
    root = state.get_state_root()

    details["nested"]["tags"].append("changed input")
    entity_snapshot = state.get_entity_state("entity-1")
    assert entity_snapshot is not None
    entity_snapshot["last_details"]["nested"]["tags"].append("changed getter")
    all_snapshot = state.get_all_states()
    all_snapshot["entity-1"]["last_details"]["nested"]["tags"].append("changed all")
    all_snapshot["entity-1"]["event_count"] = 99

    assert state.get_entity_state("entity-1")["last_details"] == {"nested": {"tags": ["original"]}}
    assert state.get_all_states()["entity-1"]["event_count"] == 1
    assert state.get_state_root() == root
