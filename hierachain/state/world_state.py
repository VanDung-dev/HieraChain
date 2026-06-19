"""
World State tracking for HieraChain Ledger.

Tracks current entity states by ingesting finalized blocks.
Provides get_entity_state() for queries and get_state_root() for proof generation.
"""

import threading
import logging
from typing import Any

from hierachain.core.block import Block
from hierachain.core.merkle_tree import MerkleTree

logger = logging.getLogger(__name__)


class WorldState:
    """
    Tracks current state of entities after block processing.

    Updated automatically when blocks are finalized via apply_block().
    State root is used by cross-level sync and proof generation.
    """

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def apply_block(self, block: Block) -> None:
        events = block.to_event_list()
        with self._lock:
            for event in events:
                entity_id = event.get("entity_id")
                if entity_id is None:
                    continue
                current = self._states.get(entity_id)
                self._states[entity_id] = self._compute_new_state(current, event)

    def apply_event_list(self, events: list[dict[str, Any]]) -> None:
        with self._lock:
            for event in events:
                entity_id = event.get("entity_id")
                if entity_id is None:
                    continue
                current = self._states.get(entity_id)
                self._states[entity_id] = self._compute_new_state(current, event)

    def get_entity_state(self, entity_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._states.get(entity_id)

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return dict(self._states)

    def get_state_root(self) -> str:
        with self._lock:
            if not self._states:
                return "0" * 64
            sorted_items = sorted(self._states.items())
            leaves = [
                {"entity_id": eid, **state}
                for eid, state in sorted_items
            ]
            return MerkleTree(leaves).get_root()

    def state_count(self) -> int:
        with self._lock:
            return len(self._states)

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

    @staticmethod
    def _compute_new_state(
        current: dict[str, Any] | None,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        if current is None:
            return {
                "entity_id": event.get("entity_id"),
                "last_event": event.get("event"),
                "last_timestamp": event.get("timestamp"),
                "last_details": event.get("details"),
                "event_count": 1,
            }
        return {
            **current,
            "last_event": event.get("event"),
            "last_timestamp": event.get("timestamp"),
            "last_details": event.get("details"),
            "event_count": current.get("event_count", 0) + 1,
        }
