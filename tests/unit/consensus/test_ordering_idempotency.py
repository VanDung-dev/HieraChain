"""Stable-ID and journal-admission contracts for the ordering facade."""

from __future__ import annotations

import threading
from queue import Queue
from types import SimpleNamespace

import pytest

from hierachain.consensus.ordering import admission, idempotency
from hierachain.consensus.ordering.types import (
    OrderingBackpressureError,
    OrderingStatus,
    PendingEvent,
)


def _event(event_id: str = "event-1", channel_id: str = "orders") -> PendingEvent:
    data = {
        "event_id": event_id,
        "entity_id": "item-1",
        "event": "created",
        "timestamp": 1.0,
        "details": {"label": "original"},
    }
    return PendingEvent(
        event_id=event_id,
        event_data=data,
        channel_id=channel_id,
        submitter_org="org-a",
        received_at=1.0,
    )


def _service(journal_result: bool = True) -> SimpleNamespace:
    calls: list[dict] = []

    def log_event(row: dict) -> bool:
        calls.append(row)
        return journal_result

    journal = SimpleNamespace(
        log_event=log_event,
        read_since=lambda: ([], (0, 0)),
        replay=lambda: [],
    )
    storage = SimpleNamespace(get_event_by_id=lambda _event_id: None)
    return SimpleNamespace(
        enqueue_timeout=0.01,
        event_pool=Queue(maxsize=1),
        pending_events={},
        should_stop=threading.Event(),
        status=OrderingStatus.ACTIVE,
        journal=journal,
        storage_handler=SimpleNamespace(processed_events={}, storage=storage),
        block_builder=None,
        _journal_lookup=None,
        journal_calls=calls,
    )


def test_fingerprint_ignores_routing_fields_but_not_content() -> None:
    base = {"event_id": "a", "channel_id": "orders", "entity_id": "item", "timestamp": 1.0}
    rerouted = {**base, "event_id": "b", "channel_id": "other"}
    changed = {**base, "timestamp": 2.0}

    assert idempotency.event_content_fingerprint(base) == idempotency.event_content_fingerprint(rerouted)
    assert idempotency.event_content_fingerprint(base) != idempotency.event_content_fingerprint(changed)


def test_same_event_commitment_rejects_channel_or_content_drift() -> None:
    candidate = _event().event_data

    with pytest.raises(ValueError, match="different content"):
        idempotency.assert_same_event("event-1", "orders", "other", candidate, candidate)
    with pytest.raises(ValueError, match="different content"):
        idempotency.assert_same_event(
            "event-1", "orders", "orders", candidate, {**candidate, "timestamp": 9.0}
        )


def test_journal_body_drops_only_routing_channel() -> None:
    row = {"event_id": "event-1", "channel_id": "orders", "event": "created"}

    assert idempotency.event_body_from_journal(row) == {
        "event_id": "event-1",
        "event": "created",
    }


def test_unknown_stable_id_reports_no_live_or_journal_match() -> None:
    service = _service()

    assert idempotency.find_stable_event(
        service, "missing", "orders", _event("missing").event_data
    ) == (None, None)


def test_admission_persists_durably_before_publishing() -> None:
    service = _service()
    event = _event()
    logged = {**event.event_data, "channel_id": event.channel_id}

    admission.enqueue_event(service, event, logged)

    assert service.journal_calls == [logged]
    assert service.pending_events == {event.event_id: event}
    assert service.event_pool.get_nowait() is event


def test_admission_journal_failure_leaves_event_unpublished() -> None:
    service = _service(journal_result=False)
    event = _event()

    with pytest.raises(RuntimeError, match="Failed to persist event event-1"):
        admission.enqueue_event(
            service, event, {**event.event_data, "channel_id": event.channel_id}
        )

    assert service.pending_events == {}
    assert service.event_pool.empty()


def test_full_queue_reports_whether_the_event_is_already_durable() -> None:
    service = _service()
    service.event_pool.put(object())
    event = _event()

    with pytest.raises(OrderingBackpressureError) as unjournaled:
        admission.enqueue_event(
            service, event, {**event.event_data, "channel_id": event.channel_id}
        )
    assert unjournaled.value.journaled is False
    assert service.journal_calls == []

    with pytest.raises(OrderingBackpressureError) as journaled:
        admission.enqueue_event(service, event)
    assert journaled.value.journaled is True
    assert service.pending_events == {}
