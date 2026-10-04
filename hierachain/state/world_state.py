"""
World State tracking for HieraChain Ledger.

Tracks current entity states by ingesting finalized blocks.
Provides entity queries and a diagnostic Merkle root of the current projection.
Cross-level proofs commit the latest block's event Merkle root instead.
"""

import logging
import threading
from copy import deepcopy
from typing import Any

from hierachain.core.block import Block
from hierachain.core.merkle_tree import MerkleTree

logger = logging.getLogger(__name__)


class WorldState:
    """
    Tracks current state of entities after block processing.

    Updated automatically when blocks are finalized via apply_block().
    The projection root is separate from the block event root anchored by proofs.
    Callers rebuilding a projection must clear it and apply each block once.
    """

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def apply_block(self, block: Block) -> None:
        events = block.to_event_list()
        with self._lock:
            for event in events:
                entity_id = event.get("entity_id")
                if not isinstance(entity_id, str):
                    continue
                current = self._states.get(entity_id)
                self._states[entity_id] = self._compute_new_state(current, event)

    def get_entity_state(self, entity_id: str) -> dict[str, Any] | None:
        """Return an independent snapshot for one entity."""
        with self._lock:
            state = self._states.get(entity_id)
            return deepcopy(state) if state is not None else None

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """Return an independent snapshot of all entity states."""
        with self._lock:
            return deepcopy(self._states)

    def get_state_root(self) -> str:
        """Return the entity projection root; this is not the cross-level proof root."""
        with self._lock:
            if not self._states:
                return "0" * 64
            snapshot = dict(self._states)
        sorted_items = sorted(snapshot.items())
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
                "last_details": deepcopy(event.get("details")),
                "event_count": 1,
            }
        return {
            **current,
            "last_event": event.get("event"),
            "last_timestamp": event.get("timestamp"),
            "last_details": deepcopy(event.get("details")),
            "event_count": current.get("event_count", 0) + 1,
        }
