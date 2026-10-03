"""Tail read-back stays durable across rotation without rescanning history."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import hierachain.error_mitigation.journal as journal_module
from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager
from hierachain.hierarchical.types import CrossChainTransaction


def _record(index: int) -> dict:
    return {"entity_id": str(index), "event": "created", "timestamp": float(index + 1)}


def test_cursor_reads_only_new_frames_and_survives_rotation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = TransactionJournal(storage_dir="tail")
    try:
        for index in range(20):
            assert journal.log_event(_record(index))
        original, cursor = journal.read_since()
        assert len(original) == 20
        assert journal.read_since(cursor) == ([], cursor)
        monkeypatch.setattr(journal_module, "_JOURNAL_MAX_FILE_SIZE", 1)
        assert journal.log_event(_record(20))
        rows, rotated_cursor = journal.read_since(cursor)
        assert [{key: row[key] for key in _record(20)} for row in rows] == [_record(20)]
        assert rotated_cursor[0] != cursor[0]
        assert journal.log_event(_record(21))
        assert [row["entity_id"] for row in journal.read_since(rotated_cursor)[0]] == [
            "21"
        ]
        journal.close()
        restarted = TransactionJournal(storage_dir="tail")
        try:
            assert [row["entity_id"] for row in restarted.read_since()[0]] == [
                str(index) for index in range(22)
            ]
        finally:
            restarted.close()
    finally:
        journal.close()


def test_tail_rejects_missing_truncated_and_corrupt_cursor_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = TransactionJournal(storage_dir="invalid-tail")
    try:
        assert journal.log_event(_record(0))
        _, cursor = journal.read_since()
        with pytest.raises(ValueError, match="missing"):
            journal.read_since((-1, 0))
        with pytest.raises(ValueError, match="truncated"):
            journal.read_since((cursor[0], cursor[1] + 1))
        with journal.active_log_file.open("ab") as handle:
            handle.write(b"\x04\x00\x00\x00nope")
        with pytest.raises(ValueError, match="Corrupt Arrow batch"):
            journal.read_since(cursor)
        journal.active_log_file.unlink()
        with pytest.raises(ValueError, match="Active journal file is missing"):
            journal.read_since()
    finally:
        journal.close()


def test_coordinator_ack_reads_new_phase_and_rejects_missing_write_or_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = TransactionJournal(storage_dir="coordinator-tail")
    try:
        for index in range(100):
            assert journal.log_event(_record(index))
        manager = CrossChainTransactionManager(SimpleNamespace(), journal=journal)
        transaction = CrossChainTransaction(
            "tx-tail", "source", "destination", {"entity_id": "item"}
        )
        original = journal.read_since
        read_counts: list[int] = []

        def observed(
            cursor: tuple[int, int] | None = None,
        ) -> tuple[list[dict], tuple[int, int]]:
            rows, next_cursor = original(cursor)
            read_counts.append(len(rows))
            return rows, next_cursor

        monkeypatch.setattr(journal, "read_since", observed)
        assert manager._journal_record(transaction, "begin")
        assert manager._journal_record(transaction, "prepared")
        assert read_counts == [1, 1]
        monkeypatch.setattr(journal, "log_event", lambda _row: True)
        assert not manager._journal_record(transaction, "commit")

        def failed_fsync(_fd: int) -> None:
            raise OSError("fsync unavailable")

        monkeypatch.setattr(os, "fsync", failed_fsync)
        assert not manager._journal_record(transaction, "commit")
        assert manager._phases[transaction.transaction_id] == "prepared"
    finally:
        journal.close()
