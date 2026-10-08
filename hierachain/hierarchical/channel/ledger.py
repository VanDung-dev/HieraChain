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
        self._storage: Any | None = None
        self._registry_revision: Callable[[], str | None] | None = None
        self._sequence = 0
        self.channel_id = channel_id

    def bind_storage(self, storage: Any, registry_revision: Callable[[], str | None]) -> None:
        """Use an initialized durable channel stream instead of registry snapshots."""
        if not callable(getattr(storage, "append_channel_record", None)) or not callable(
            getattr(storage, "load_channel_records", None)
        ):
            raise RuntimeError("Storage does not support durable channel ledgers")
        self._storage = storage
        self._registry_revision = registry_revision

    def refresh(self) -> list[dict[str, Any]]:
        """Validate and apply only unseen durable records, returning new accepted events."""
        if self._storage is None:
            return []
        with self._lock:
            suffix = self._storage.load_channel_records(self.channel_id, after_sequence=self._sequence)
            if (
                not isinstance(suffix, dict) or not isinstance(suffix.get("revision"), int)
                or not isinstance(suffix.get("records"), list)
                or suffix["revision"] - self._sequence != len(suffix["records"])
            ):
                raise RuntimeError("Invalid durable channel ledger suffix")
            previous_blocks, previous_pending = self.blocks, self.current_block_events
            block_count, pending_count = len(previous_blocks), len(previous_pending)
            previous_sequence, previous_hash = self._sequence, self.last_block_hash
            accepted = []
            try:
                for record in suffix["records"]:
                    accepted.extend(self._replay_record(record))
                    self._sequence += 1
            except Exception:
                # Roll back only newly applied records, without copying old history.
                del previous_blocks[block_count:]
                del previous_pending[pending_count:]
                self.blocks, self.current_block_events = previous_blocks, previous_pending
                self.height, self.last_block_hash = block_count, previous_hash
                self._sequence = previous_sequence
                raise
            return accepted

    def _replay_record(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(record, dict):
            raise RuntimeError("Invalid durable channel ledger record")
        kind, data = record.get("kind"), record.get("data")
        if kind == "snapshot" and self._sequence == 0:
            self.restore(data)
            return [event for block in self.blocks for event in block.to_event_list()] + list(self.current_block_events)
        if self._sequence == 0:
            raise RuntimeError("Durable channel ledger is missing its initial snapshot")
        if kind == "event":
            self._validate_pending_event(data)
            self.current_block_events.append(deepcopy(data))
            return [data]
        if kind == "block":
            try:
                block = Block.from_dict(data)
                self._validate_block(block, self.height, self.blocks[-1] if self.blocks else None)
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError("Invalid signed channel block history") from exc
            if not self.current_block_events or block.to_event_list() != self.current_block_events:
                raise RuntimeError("Channel block does not match durable pending events")
            self.blocks.append(block)
            self.height += 1
            self.last_block_hash = block.hash
            self.current_block_events = []
            return []
        raise RuntimeError("Invalid durable channel ledger record")

    def _validate_pending_event(self, event: Any) -> None:
        if (
            not isinstance(event, dict) or not event.get("entity_id") or not event.get("event")
            or (self.channel_id is not None and event.get("channel_id") != self.channel_id)
        ):
            raise RuntimeError("Invalid pending channel event")

    def _validate_block(self, block: Block, index: int, previous: Block | None) -> None:
        public_key = self.trusted_public_keys.get(block.creator_id)
        if (
            block.index != index or (index == 0 and block.previous_hash != "0") or public_key is None
            or not get_block_verifier().verify_block(block, previous, public_key).is_valid
            or (
                self.channel_id is not None
                and any(event.get("channel_id") != self.channel_id for event in block.to_event_list())
            )
        ):
            raise RuntimeError("Invalid signed channel block history")

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
        for index, block in enumerate(blocks):
            previous = blocks[index - 1] if index else None
            self._validate_block(block, index, previous)
        for event in pending:
            self._validate_pending_event(event)
        with self._lock:
            self.blocks = blocks
            self.current_block_events = deepcopy(pending)
            self.height = len(blocks)
            self.last_block_hash = blocks[-1].hash if blocks else "0"

    def _save(self, record: dict[str, Any]) -> bool:
        """A managed ledger must persist successfully before acknowledging a change."""
        if self._storage is None:
            return True
        revision = self._registry_revision() if self._registry_revision is not None else None
        if self._storage.append_channel_record(
            self.channel_id, record, expected_sequence=self._sequence, expected_registry_revision=revision,
        ) is not True:
            raise RuntimeError("Failed to persist channel ledger")
        self._sequence += 1
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
            self._save({"kind": "event", "data": accepted})
            self.current_block_events.append(accepted)
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

        self._save({"kind": "block", "data": block.to_dict()})
        self.blocks.append(block)
        self.height += 1
        self.last_block_hash = block.hash
        self.current_block_events = []
        return block

    def get_events_by_filter(
        self, filter_func, filter_expr: Any | None = None
    ) -> list[dict[str, Any]]:
        events = []
        for block in self.blocks:
            events.extend(_filter_block_events(block, filter_func, filter_expr))
        return events
