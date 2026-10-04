"""Incremental stable-ID lookup over the durable ordering journal."""

import hashlib
import threading
from collections.abc import Callable
from typing import Any


class JournalEventLookup:
    """Keep ID/channel/content commitments, without retaining journal payloads."""

    def __init__(self, journal: Any, fingerprint: Callable[[dict[str, Any]], bytes]) -> None:
        self.journal = journal
        self.fingerprint = fingerprint
        self._lock = threading.Lock()
        self._cursor: tuple[int, int] | None = None
        self._entries: dict[str, tuple[str, bytes] | None] = {}

    def find(
        self, event_id: str, channel_id: str, candidate: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Read new frames, reject conflicting IDs, and return a matching record.

        A hit already represented in live ordering/storage never reaches here.
        An older journal-only hit still reads history to recover its payload.
        """
        with self._lock:
            rows, cursor = self.journal.read_since(self._cursor)
            updates: dict[str, tuple[str, bytes] | None] = {}
            matching_row = None
            for row in rows:
                row_id = row.get("event_id")
                if not isinstance(row_id, str):
                    continue
                channel = row.get("channel_id")
                entry = (
                    (channel, hashlib.sha256(self.fingerprint(row)).digest())
                    if isinstance(channel, str) else None
                )
                if row_id in updates or row_id in self._entries:
                    previous = updates.get(row_id, self._entries.get(row_id))
                    if previous != entry:
                        entry = None
                updates[row_id] = entry
                if row_id == event_id:
                    matching_row = row
            # A failed tail read/fingerprint must not advance the snapshot.
            self._entries.update(updates)
            self._cursor = cursor
            if event_id not in self._entries:
                return None
            expected = (channel_id, hashlib.sha256(self.fingerprint(candidate)).digest())
            if self._entries[event_id] != expected:
                raise ValueError(f"Event ID {event_id} is already bound to different content")
            if matching_row is not None:
                return matching_row

            # Retain only compact commitments. Recover an older orphan's full
            # payload from disk, validating every occurrence before requeueing.
            history, _ = self.journal.read_since()
            for row in history:
                if row.get("event_id") != event_id:
                    continue
                actual = (row.get("channel_id"), hashlib.sha256(self.fingerprint(row)).digest())
                if actual != expected:
                    raise ValueError(f"Event ID {event_id} is already bound to different content")
                matching_row = row
            if matching_row is None:
                raise ValueError(f"Event ID {event_id} is missing from the journal")
            return matching_row
