"""
ChannelLedger — block storage and event journaling for channels.
"""

import logging
import threading
import time
from copy import deepcopy
from typing import Any, Callable

from hierachain.core.block import Block, convert_events_to_arrow
from hierachain.hierarchical.channel.query import _filter_block_events
from hierachain.security.identity_loader import NodeIdentity, require_block_identity
from hierachain.security.verify.block_verifier import get_block_verifier, sign_block

logger = logging.getLogger(__name__)


class ChannelLedger:
    def __init__(
        self,
        node_identity: NodeIdentity | None = None,
        trusted_public_keys: dict[str, bytes] | None = None,
        channel_id: str | None = None,
    ) -> None:
        self.node_identity, self.trusted_public_keys = require_block_identity(
            node_identity, trusted_public_keys
        )
        self.blocks: list[Block] = []
        self.current_block_events: list[dict[str, Any]] = []
        self.height = 0
        self.last_block_hash = "0"
        self._lock = threading.RLock()
        self._persist: Callable[[], bool] | None = None
        self.channel_id = channel_id

    def snapshot(self) -> dict[str, Any]:
        """Export both committed blocks and accepted events for durable recovery."""
        with self._lock:
            return {
                "blocks": [block.to_dict() for block in self.blocks],
                "pending_events": deepcopy(self.current_block_events),
            }

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Validate the complete signed history before replacing local state."""
        if not isinstance(snapshot, dict):
            raise RuntimeError("Invalid channel ledger snapshot")
        rows = snapshot.get("blocks")
        pending = snapshot.get("pending_events")
        if not isinstance(rows, list) or not isinstance(pending, list):
            raise RuntimeError("Invalid channel ledger snapshot")
        try:
            blocks = [Block.from_dict(row) for row in rows]
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Invalid signed channel block history") from exc
        verifier = get_block_verifier()
        for index, block in enumerate(blocks):
            previous = blocks[index - 1] if index else None
            public_key = self.trusted_public_keys.get(block.creator_id)
            if (
                block.index != index
                or (index == 0 and block.previous_hash != "0")
                or public_key is None
                or not verifier.verify_block(block, previous, public_key).is_valid
                or (
                    self.channel_id is not None
                    and any(event.get("channel_id") != self.channel_id for event in block.to_event_list())
                )
            ):
                raise RuntimeError("Invalid signed channel block history")
        if any(
            not isinstance(event, dict) or not event.get("entity_id") or not event.get("event")
            or (self.channel_id is not None and event.get("channel_id") != self.channel_id)
            for event in pending
        ):
            raise RuntimeError("Invalid pending channel event")
        with self._lock:
            self.blocks = blocks
            self.current_block_events = deepcopy(pending)
            self.height = len(blocks)
            self.last_block_hash = blocks[-1].hash if blocks else "0"

    def _save(self) -> bool:
        """A managed ledger must persist successfully before acknowledging a change."""
        if self._persist is None:
            return True
        if self._persist() is not True:
            raise RuntimeError("Failed to persist channel ledger")
        return True

    def add_event(self, event: dict[str, Any]) -> bool:
        if not isinstance(event, dict):
            logger.warning("ChannelLedger: Rejected event - not a dict")
            return False

        if "entity_id" not in event or not event.get("entity_id"):
            logger.warning("ChannelLedger: Rejected event - missing entity_id")
            return False

        if "event" not in event or not event.get("event"):
            logger.warning("ChannelLedger: Rejected event - missing event type")
            return False

        with self._lock:
            accepted = deepcopy(event)
            if self.channel_id is not None:
                accepted["channel_id"] = self.channel_id
            accepted["timestamp"] = accepted.get("timestamp", time.time())
            accepted["channel_event"] = True
            self.current_block_events.append(accepted)
            try:
                self._save()
            except Exception:
                self.current_block_events.pop()
                raise
            return True

    def finalize_block(self) -> Block | None:
        with self._lock:
            return self._finalize_block()

    def _finalize_block(self) -> Block | None:
        if not self.current_block_events:
            return None

        table = convert_events_to_arrow(self.current_block_events)

        block = Block(
            index=self.height,
            events=table,
            timestamp=time.time(),
            previous_hash=self.last_block_hash,
        )
        sign_block(
            block, self.node_identity.node_id, self.node_identity.signing_keypair
        )
        public_key = self.trusted_public_keys[self.node_identity.node_id]
        if not get_block_verifier().verify_block(block, public_key=public_key).is_valid:
            raise ValueError("Channel block signature verification failed")

        pending = self.current_block_events
        previous_hash = self.last_block_hash
        self.blocks.append(block)
        self.height += 1
        self.last_block_hash = block.hash
        self.current_block_events = []
        try:
            self._save()
        except Exception:
            self.blocks.pop()
            self.height -= 1
            self.last_block_hash = previous_hash
            self.current_block_events = pending
            raise

        return block

    def get_events_by_filter(
        self, filter_func, filter_expr: Any | None = None
    ) -> list[dict[str, Any]]:
        events = []
        for block in self.blocks:
            events.extend(_filter_block_events(block, filter_func, filter_expr))
        return events
