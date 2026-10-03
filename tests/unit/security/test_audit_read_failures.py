"""Audit searches must distinguish missing evidence from unreadable evidence."""

import struct
from pathlib import Path

import pyarrow as pa
import pytest

from hierachain.risk_management import audit_logger as module
from hierachain.risk_management.audit_logger import (
    ArrowAuditStorage,
    AuditEvent,
    AuditEventType,
    AuditFilter,
    AuditSeverity,
    DatabaseAuditStorage,
    FileAuditStorage,
)


def _event() -> AuditEvent:
    return AuditEvent(
        event_id="readable", event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING, timestamp=1.0, source_component="test",
        description="Retained evidence", details={},
    )


@pytest.mark.parametrize("backend", ["sqlite", "arrow", "file"])
def test_valid_empty_audit_search_remains_empty(tmp_path: Path, backend: str) -> None:
    storage = {
        "sqlite": lambda: DatabaseAuditStorage(str(tmp_path / "audit.sqlite")),
        "arrow": lambda: ArrowAuditStorage(str(tmp_path)),
        "file": lambda: FileAuditStorage(str(tmp_path)),
    }[backend]()
    try:
        assert storage.retrieve_events(AuditFilter()) == []
        assert storage.get_event_count(AuditFilter()) == 0
    finally:
        if isinstance(storage, ArrowAuditStorage):
            storage.close()


def test_malformed_sqlite_audit_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "audit.sqlite"
    storage = DatabaseAuditStorage(str(path))
    path.write_bytes(b"invalid database")
    with pytest.raises(RuntimeError, match="retrieve audit events from DB"):
        storage.retrieve_events(AuditFilter())
    with pytest.raises(RuntimeError, match="count audit events in DB"):
        storage.get_event_count(AuditFilter())


@pytest.mark.parametrize("backend", ["file", "arrow"])
def test_corrupt_jsonl_after_valid_event_never_returns_partial_result(tmp_path: Path, backend: str) -> None:
    storage = FileAuditStorage(str(tmp_path)) if backend == "file" else ArrowAuditStorage(str(tmp_path))
    (tmp_path / "audit_legacy.jsonl").write_text(_event().to_json() + "\n{malformed\n", encoding="utf-8")
    try:
        with pytest.raises(RuntimeError, match="retrieve audit"):
            storage.retrieve_events(AuditFilter())
        with pytest.raises(RuntimeError):
            storage.get_event_count(AuditFilter())
    finally:
        if isinstance(storage, ArrowAuditStorage):
            storage.close()


@pytest.mark.parametrize("tail", [b"\x01", struct.pack("<I", 20) + b"partial"])
def test_legacy_arrow_truncated_tail_never_returns_acknowledged_prefix(tmp_path: Path, tail: bytes) -> None:
    storage = ArrowAuditStorage(str(tmp_path))
    batch = pa.RecordBatch.from_pylist([module._audit_event_to_row(_event())], schema=module._AUDIT_SCHEMA)
    payload = batch.serialize().to_pybytes()
    (tmp_path / "audit_legacy.arrow").write_bytes(struct.pack("<I", len(payload)) + payload + tail)
    try:
        with pytest.raises(RuntimeError, match="retrieve audit archive"):
            storage.retrieve_events(AuditFilter())
        with pytest.raises(RuntimeError, match="count audit archive"):
            storage.get_event_count(AuditFilter())
    finally:
        storage.close()


def test_corrupt_parquet_is_not_reinterpreted_as_legacy_arrow(tmp_path: Path) -> None:
    storage = ArrowAuditStorage(str(tmp_path))
    (tmp_path / "audit_broken.parquet").write_bytes(b"broken parquet")
    try:
        with pytest.raises(RuntimeError, match="retrieve audit archive"):
            storage.retrieve_events(AuditFilter())
        with pytest.raises(RuntimeError, match="count audit archive"):
            storage.get_event_count(AuditFilter())
    finally:
        storage.close()


def test_snapshot_close_failure_is_not_an_empty_audit_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = ArrowAuditStorage(str(tmp_path))
    assert storage.store_event(_event())

    class FailingWriter:
        def close(self) -> None:
            raise OSError("Failed to persist Parquet footer")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(storage, "_pq_writer", FailingWriter())
            with pytest.raises(RuntimeError, match="retrieve audit archive"):
                storage.retrieve_events(AuditFilter())
            with pytest.raises(RuntimeError, match="count audit archive"):
                storage.get_event_count(AuditFilter())
        assert len(storage.retrieve_events(AuditFilter())) == 1
    finally:
        storage.close()
