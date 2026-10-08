"""Read-back reuses only file states already covered by a successful fsync."""

import os
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from hierachain.error_mitigation.journal import TransactionJournal


@pytest.fixture
def journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TransactionJournal, None, None]:
    monkeypatch.chdir(tmp_path)
    writer = TransactionJournal(storage_dir="sync-state")
    try:
        yield writer
    finally:
        writer.close()


def _event() -> dict[str, Any]:
    return {"entity_id": "probe", "event": "created", "timestamp": 1.0}


def test_acknowledged_append_has_one_sync_and_still_reads_from_disk(
    journal: TransactionJournal, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    original = os.fsync

    def counted(fd: int) -> None:
        calls.append(fd)
        original(fd)

    monkeypatch.setattr(os, "fsync", counted)
    assert journal.log_event(_event())
    rows, cursor = journal.read_since()
    assert rows[0]["event"] == "created"
    assert journal.read_since(cursor) == ([], cursor)
    assert len(calls) == 1
    # An explicit flush retains its synchronization contract.
    journal.flush()
    assert len(calls) == 2


def test_reopened_file_requires_a_new_sync_before_read_back(
    journal: TransactionJournal, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert journal.log_event(_event())
    journal.close()
    reopened = TransactionJournal(storage_dir="sync-state")
    original = os.fsync
    calls = []

    def counted(fd: int) -> None:
        calls.append(fd)
        original(fd)

    monkeypatch.setattr(os, "fsync", counted)
    try:
        rows, cursor = reopened.read_since()
        assert rows[0]["event"] == "created"
        assert reopened.read_since(cursor) == ([], cursor)
        assert len(calls) == 1
    finally:
        reopened.close()


@pytest.mark.parametrize("same_size", [False, True])
def test_untracked_file_change_requires_sync_and_propagates_sync_failure(
    journal: TransactionJournal, monkeypatch: pytest.MonkeyPatch, same_size: bool,
) -> None:
    assert journal.log_event(_event())
    _, cursor = journal.read_since()
    before = journal.active_log_file.stat()
    with journal.active_log_file.open("r+b") as handle:
        if same_size:
            first = handle.read(1)
            handle.seek(0)
            handle.write(first)
        else:
            handle.seek(0, os.SEEK_END)
            handle.write(b"pending")
    os.utime(journal.active_log_file, ns=(before.st_atime_ns, before.st_mtime_ns + 1))

    def failed(_fd: int) -> None:
        raise OSError("injected unsynced change")

    monkeypatch.setattr(os, "fsync", failed)
    with pytest.raises(OSError, match="injected unsynced change"):
        journal.read_since(cursor)
    assert journal._synced_file_state is None


def test_failed_append_and_rollback_never_reuse_old_sync_state(
    journal: TransactionJournal, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert journal.log_event(_event())
    original = os.fsync

    def failed(_fd: int) -> None:
        raise OSError("injected sync failure")

    monkeypatch.setattr(os, "fsync", failed)
    assert journal.log_event(_event()) is False
    assert journal._synced_file_state is None
    assert journal._write_poisoned
    with pytest.raises(OSError, match="injected sync failure"):
        journal.read_since()
    monkeypatch.setattr(os, "fsync", original)
    assert len(journal.read_since()[0]) == 1
    assert journal.log_event(_event()) is False


def test_replaced_active_path_cannot_reuse_another_inode_sync_state(
    journal: TransactionJournal,
) -> None:
    assert journal.log_event(_event())
    data = journal.active_log_file.read_bytes()
    old_file = journal.active_log_file.with_name("replaced.arrow")
    journal.active_log_file.rename(old_file)
    journal.active_log_file.write_bytes(data)

    with pytest.raises(ValueError, match="replaced"):
        journal.read_since()


def test_read_back_cannot_finish_while_append_is_waiting_for_fsync(
    journal: TransactionJournal, monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    release = threading.Event()
    read_started = threading.Event()
    read_finished = threading.Event()
    original = os.fsync

    def blocked(fd: int) -> None:
        started.set()
        if not release.wait(3):
            raise OSError("test sync release timeout")
        original(fd)

    def read() -> list[dict[str, Any]]:
        read_started.set()
        rows, _ = journal.read_since()
        read_finished.set()
        return rows

    monkeypatch.setattr(os, "fsync", blocked)
    with ThreadPoolExecutor(max_workers=2) as workers:
        append = workers.submit(journal.log_event, _event())
        try:
            assert started.wait(3)
            reader = workers.submit(read)
            assert read_started.wait(3)
            assert not read_finished.wait(0.05)
        finally:
            release.set()
        assert append.result(timeout=3) is True
        assert reader.result(timeout=3)[0]["event"] == "created"
