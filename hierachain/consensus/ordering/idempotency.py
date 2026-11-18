"""Stable ordering event identity across pending, batch, storage and journal tiers."""

from __future__ import annotations

from typing import Any

from hierachain.consensus.ordering.types import PendingEvent
from hierachain.consensus.ordering.utils import make_serializable
from hierachain.serialization import dumps_canonical_json


def event_content_fingerprint(event_data: dict[str, Any]) -> bytes:
    if not isinstance(event_data, dict):
        raise ValueError("event content must be a dictionary")
    content = {
        key: value
        for key, value in event_data.items()
        if key not in {"event_id", "channel_id"}
    }
    return dumps_canonical_json(make_serializable(content))


def assert_same_event(
    event_id: str,
    channel_id: str,
    existing_channel_id: Any,
    existing_data: Any,
    candidate_data: dict[str, Any],
) -> None:
    if existing_channel_id != channel_id or not isinstance(existing_data, dict):
        raise ValueError(f"Event ID {event_id} is already bound to different content")
    if event_content_fingerprint(existing_data) != event_content_fingerprint(
        candidate_data
    ):
        raise ValueError(f"Event ID {event_id} is already bound to different content")


def event_body_from_journal(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "channel_id"}


def is_live_duplicate(service: Any, event: PendingEvent) -> bool:
    existing = service.pending_events.get(event.event_id)
    if existing is not None:
        assert_same_event(
            event.event_id, event.channel_id, existing.channel_id,
            existing.event_data, event.event_data,
        )
        return True

    builder = getattr(service, "block_builder", None)
    if event.event_id in getattr(builder, "current_batch_ids", set()):
        batched = next(
            (
                item for item in getattr(builder, "current_batch", [])
                if item.event_id == event.event_id
            ),
            None,
        )
        if batched is None:
            raise ValueError(
                f"Cannot verify existing event content for ID {event.event_id}"
            )
        assert_same_event(
            event.event_id, event.channel_id, batched.channel_id,
            batched.event_data, event.event_data,
        )
        return True

    processed = service.storage_handler.processed_events.get(event.event_id)
    if processed is not None:
        assert_same_event(
            event.event_id, event.channel_id, processed.channel_id,
            processed.event_data, event.event_data,
        )
        return True
    return False


def find_stable_event(
    service: Any,
    event_id: str,
    channel_id: str,
    candidate_data: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    found_kind: str | None = None

    pending = service.pending_events.get(event_id)
    if pending is not None:
        assert_same_event(
            event_id, channel_id, pending.channel_id,
            pending.event_data, candidate_data,
        )
        found_kind = "pending"

    builder = getattr(service, "block_builder", None)
    if event_id in getattr(builder, "current_batch_ids", set()):
        batched = next(
            (
                item for item in getattr(builder, "current_batch", [])
                if item.event_id == event_id
            ),
            None,
        )
        if batched is None:
            raise ValueError(
                f"Cannot verify existing event content for ID {event_id}"
            )
        assert_same_event(
            event_id, channel_id, batched.channel_id,
            batched.event_data, candidate_data,
        )
        found_kind = found_kind or "batch"

    processed = service.storage_handler.processed_events.get(event_id)
    if processed is not None:
        assert_same_event(
            event_id, channel_id, processed.channel_id,
            processed.event_data, candidate_data,
        )
        found_kind = found_kind or "processed"

    stored = service.storage_handler.storage.get_event_by_id(event_id)
    if stored is not None:
        stored_data = stored.get("data")
        assert_same_event(
            event_id, channel_id, stored.get("chain_name"),
            stored_data, candidate_data,
        )
        if not isinstance(stored_data, dict) or stored_data.get("event_id") != event_id:
            raise ValueError(
                f"Cannot verify existing event content for ID {event_id}"
            )
        found_kind = found_kind or "stored"

    if found_kind is not None:
        return found_kind, None

    read_since = getattr(service.journal, "read_since", None)
    lookup = getattr(service, "_journal_lookup", None)
    if callable(read_since) and lookup is not None and lookup.journal is service.journal:
        row = lookup.find(event_id, channel_id, candidate_data)
        return ("journal", row) if row is not None else (None, None)
    if callable(read_since):
        journal_rows, _ = read_since()
    else:
        journal_rows = list(service.journal.replay())
    matching_journal_row: dict[str, Any] | None = None
    for row in journal_rows:
        if row.get("event_id") != event_id:
            continue
        assert_same_event(
            event_id, channel_id, row.get("channel_id"), row,
            candidate_data,
        )
        matching_journal_row = row

    if matching_journal_row is not None:
        return "journal", matching_journal_row
    return None, None
