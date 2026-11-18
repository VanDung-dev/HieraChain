"""Reserve ordering capacity, then persist durably before publishing the event."""

from __future__ import annotations

import time
from typing import Any

from hierachain.consensus.ordering.idempotency import is_live_duplicate
from hierachain.consensus.ordering.types import (
    OrderingBackpressureError,
    OrderingStatus,
    PendingEvent,
)


def enqueue_event(
    service: Any,
    event: PendingEvent,
    journal_data: dict[str, Any] | None = None,
) -> None:
    deadline = time.monotonic() + service.enqueue_timeout
    pool = service.event_pool
    with pool.not_full:
        if is_live_duplicate(service, event):
            return
        while pool.maxsize > 0 and pool._qsize() >= pool.maxsize:
            remaining = deadline - time.monotonic()
            if (
                remaining <= 0
                or service.should_stop.is_set()
                or service.status != OrderingStatus.ACTIVE
            ):
                raise OrderingBackpressureError(
                    event.event_id, journaled=journal_data is None
                )
            pool.not_full.wait(min(remaining, 0.05))
        if service.should_stop.is_set() or service.status != OrderingStatus.ACTIVE:
            raise OrderingBackpressureError(
                event.event_id, journaled=journal_data is None
            )
        if journal_data is not None and not service.journal.log_event(journal_data):
            raise RuntimeError(
                f"Failed to persist event {event.event_id} to the journal"
            )
        service.pending_events[event.event_id] = event
        pool._put(event)
        pool.unfinished_tasks += 1
        pool.not_empty.notify()
