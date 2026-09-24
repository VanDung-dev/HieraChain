from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from hierachain.core import parquet_log
from hierachain.risk_management import audit_logger
from hierachain.risk_management.audit_logger import ArrowAuditStorage
from hierachain.risk_management.types import (
    AuditEvent,
    AuditEventType,
    AuditFilter,
    AuditSeverity,
)


def test_parquet_log_appends_segments_and_reads_legacy_file(tmp_path, monkeypatch):
    path = tmp_path / "events.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [{"timestamp": 0.0, "data": '{"id":0}'}], schema=parquet_log._SCHEMA
        ),
        path,
    )
    monkeypatch.setattr(parquet_log, "_ROW_GROUP_ROWS", 2)
    monkeypatch.setattr(parquet_log, "_SEGMENT_ROWS", 2)
    reads: list[Path] = []
    read_table = pq.read_table

    def track_reads(source, *args, **kwargs):
        reads.append(Path(source))
        return read_table(source, *args, **kwargs)

    monkeypatch.setattr(parquet_log.pq, "read_table", track_reads)
    for record_id in range(1, 6):
        parquet_log.write_parquet_log(path, {"id": record_id, "timestamp": record_id})

    assert reads == []
    result = parquet_log.read_parquet_log(path)

    assert result.column("timestamp").to_pylist() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    assert len(reads) == 4  # one legacy file and three finalized segments


def test_audit_retrieval_does_not_replay_active_file(tmp_path, monkeypatch):
    storage = ArrowAuditStorage(str(tmp_path))
    reads: list[Path] = []
    read_table = pq.read_table

    def track_reads(source, *args, **kwargs):
        reads.append(Path(source))
        return read_table(source, *args, **kwargs)

    monkeypatch.setattr(audit_logger.pq, "read_table", track_reads)
    first = AuditEvent(
        "first",
        AuditEventType.SYSTEM_EVENT,
        AuditSeverity.INFO,
        1.0,
        "test",
        "first event",
        {},
    )
    second = AuditEvent(
        "second",
        AuditEventType.SYSTEM_EVENT,
        AuditSeverity.INFO,
        2.0,
        "second",
        "second event",
        {},
    )

    try:
        assert storage.store_event(first)
        assert [event.event_id for event in storage.retrieve_events(AuditFilter())] == [
            "first"
        ]
        assert len(reads) == 1
        assert storage._pq_writer is not None

        assert storage.store_event(second)
        assert len(reads) == 1
        assert [
            event.event_id
            for event in storage.retrieve_events(
                AuditFilter(source_components=["second"]), limit=1
            )
        ] == ["second"]
        assert storage._pq_writer is not None
    finally:
        storage.close()
