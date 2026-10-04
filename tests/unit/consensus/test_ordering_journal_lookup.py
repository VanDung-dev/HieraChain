"""Stable-ID admission uses durable suffixes without rescanning normal history."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.types import OrderingStatus


def _event(event_id: str, label: str = "original") -> dict[str, Any]:
    return {
        "event_id": event_id, "entity_id": event_id, "event": "created",
        "timestamp": 1.0, "details": {"label": label},
    }


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[OrderingService, None, None]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(OrderingService, "_start_processing_thread", lambda _self: None)
    ordering = OrderingService({
        "db_url": "sqlite:///" + str(tmp_path / "ordering.db"),
        "chain_name": "orders", "storage_dir": "lookup",
    })
    ordering.status = OrderingStatus.ACTIVE
    try:
        yield ordering
    finally:
        ordering.shutdown()


def test_new_stable_ids_decode_history_once_then_only_new_records(
    service: OrderingService, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for index in range(30):
        assert service.journal.log_event({**_event(f"old-{index}"), "channel_id": "orders"})
    read_counts = []
    original = service.journal.read_since

    def observed(cursor: tuple[int, int] | None = None) -> tuple[list[dict], tuple[int, int]]:
        rows, next_cursor = original(cursor)
        read_counts.append(len(rows))
        return rows, next_cursor

    monkeypatch.setattr(service.journal, "read_since", observed)
    for index in range(3):
        assert service.receive_event(_event(f"new-{index}"), "orders", "org-a") == f"new-{index}"

    assert read_counts == [30, 1, 1]
    assert service.receive_event(_event("new-0"), "orders", "org-a") == "new-0"
    assert read_counts == [30, 1, 1]
    assert service.event_pool.qsize() == 3
    # The index retains commitments, not copies of historical payloads.
    assert all(entry is None or len(entry[1]) == 32 for entry in service._journal_lookup._entries.values())


@pytest.mark.parametrize("warm_before_append", [False, True])
def test_orphaned_durable_event_is_requeued_without_a_second_append(
    service: OrderingService, warm_before_append: bool,
) -> None:
    if warm_before_append:
        assert service._find_stable_event("missing", "orders", _event("missing")) == (None, None)
    event = _event("orphan")
    assert service.journal.log_event({**event, "channel_id": "orders"})
    if not warm_before_append:
        # Warm on another ID; the orphan's payload is then recovered from disk.
        assert service._find_stable_event("missing", "orders", _event("missing")) == (None, None)

    assert service.receive_event(event, "orders", "org-a") == "orphan"
    assert service.event_pool.get_nowait().event_data == event
    assert len(service.journal.read_since()[0]) == 1


@pytest.mark.parametrize("conflict", ["content", "channel"])
def test_conflicting_historical_id_is_rejected_even_when_latest_record_matches(
    service: OrderingService, conflict: str,
) -> None:
    event = _event("conflict")
    assert service.journal.log_event({**event, "channel_id": "orders"})
    assert service._find_stable_event("missing", "orders", _event("missing")) == (None, None)
    changed = _event("conflict", "changed") if conflict == "content" else event
    channel = "other" if conflict == "channel" else "orders"
    assert service.journal.log_event({**changed, "channel_id": channel})

    with pytest.raises(ValueError, match="different content"):
        service.receive_event(changed, channel, "org-a")
    assert service.event_pool.empty()


def test_failed_tail_read_does_not_advance_lookup_and_retry_sees_the_orphan(
    service: OrderingService, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert service._find_stable_event("missing", "orders", _event("missing")) == (None, None)
    cursor = service._journal_lookup._cursor
    original = service.journal.read_since
    event = _event("orphan")
    assert service.journal.log_event({**event, "channel_id": "orders"})

    def unavailable(_cursor: tuple[int, int] | None = None) -> None:
        raise OSError("injected read failure")

    monkeypatch.setattr(service.journal, "read_since", unavailable)
    with pytest.raises(OSError, match="injected read failure"):
        service.receive_event(event, "orders", "org-a")
    assert service._journal_lookup._cursor == cursor
    assert service.event_pool.empty()
    monkeypatch.setattr(service.journal, "read_since", original)
    assert service.receive_event(event, "orders", "org-a") == "orphan"
    assert len(service.journal.read_since()[0]) == 1


def test_lookup_survives_rotation_and_rejects_a_removed_cursor(
    service: OrderingService, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hierachain.error_mitigation.journal as journal_module

    assert service.journal.log_event({**_event("old"), "channel_id": "orders"})
    assert service._find_stable_event("missing", "orders", _event("missing")) == (None, None)
    old_file = service.journal.active_log_file
    old_inode = old_file.stat().st_ino
    monkeypatch.setattr(journal_module, "_JOURNAL_MAX_FILE_SIZE", 1)
    assert service.journal.log_event({**_event("new"), "channel_id": "orders"})
    assert service.receive_event(_event("new"), "orders", "org-a") == "new"
    assert service._journal_lookup._cursor[0] != old_inode
    service.journal.active_log_file.unlink()
    with pytest.raises(ValueError, match="missing"):
        service.receive_event(_event("later"), "orders", "org-a")


def test_replaced_replay_only_journal_keeps_the_compatibility_lookup(
    service: OrderingService,
) -> None:
    class LegacyJournal:
        def replay(self) -> list[dict[str, Any]]:
            return [{**_event("legacy"), "channel_id": "orders"}]

    original = service.journal
    service.journal = LegacyJournal()
    try:
        assert service.receive_event(_event("legacy"), "orders", "org-a") == "legacy"
        assert service.event_pool.get_nowait().event_data == _event("legacy")
        with pytest.raises(ValueError, match="different content"):
            service.receive_event(_event("legacy", "changed"), "orders", "org-a")
    finally:
        service.journal = original
