"""Regressions for audit storage and trusted-manifest findings."""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pytest

from hierachain.risk_management import audit_logger as audit_logger_module
from hierachain.risk_management.audit_logger import (
    ArrowAuditStorage,
    AuditEvent,
    AuditEventType,
    AuditFilter,
    AuditIntegrityStatus,
    AuditLogger,
    AuditSeverity,
    DatabaseAuditStorage,
    FileAuditStorage,
    verify_integrity,
)
from hierachain.serialization import dumps_canonical_json


def _event(event_id: str, timestamp: float, description: str = "audit") -> AuditEvent:
    return AuditEvent(
        event_id=event_id,
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=timestamp,
        source_component="test",
        description=description,
        details={},
    )


def test_file_audit_range_visits_each_local_date_across_midnight(tmp_path: Path) -> None:
    before = time.mktime((2026, 1, 12, 23, 59, 0, 0, 0, -1))
    after = time.mktime((2026, 1, 13, 0, 1, 0, 0, 0, -1))
    storage = FileAuditStorage(str(tmp_path))
    assert storage.store_event(_event("before-midnight", before))
    assert storage.store_event(_event("after-midnight", after))

    events = storage.retrieve_events(AuditFilter(time_range=(before, after)))

    assert {event.event_id for event in events} == {"before-midnight", "after-midnight"}
    assert storage.get_event_count(AuditFilter(time_range=(before, after))) == 2


@pytest.mark.parametrize("backend", ["sqlite", "arrow"])
def test_database_and_arrow_storage_use_shared_arrow_sanitization(
    tmp_path: Path, backend: str,
) -> None:
    arrow_value = pa.table({"item": [1]})
    event = AuditEvent(
        event_id=f"arrow-{backend}",
        event_type=AuditEventType.SYSTEM_EVENT,
        severity=AuditSeverity.INFO,
        timestamp=1.0,
        source_component="test",
        description="Arrow payload",
        details={"nested": {"table": arrow_value}},
        affected_entities=[arrow_value],
    )
    storage = (
        DatabaseAuditStorage(str(tmp_path / "audit.sqlite"))
        if backend == "sqlite"
        else ArrowAuditStorage(str(tmp_path / "arrow"))
    )
    try:
        assert storage.store_event(event)
        stored = storage.retrieve_events(AuditFilter())
        expected = event.to_dict()
        assert len(stored) == 1
        assert stored[0].details == expected["details"]
        assert stored[0].affected_entities == expected["affected_entities"]
    finally:
        if isinstance(storage, ArrowAuditStorage):
            storage.close()


@pytest.mark.parametrize("backend", ["sqlite", "arrow"])
def test_integer_timestamps_round_trip_and_accept_legacy_digest(
    tmp_path: Path, backend: str,
) -> None:
    event = _event(f"integer-{backend}", 1)
    storage = (
        DatabaseAuditStorage(str(tmp_path / "integer.sqlite"))
        if backend == "sqlite"
        else ArrowAuditStorage(str(tmp_path / "integer-arrow"))
    )
    legacy_data = event.to_dict()
    legacy_data["timestamp"] = 1
    legacy_digest = hashlib.sha256(
        dumps_canonical_json(legacy_data, default=str)
    ).hexdigest()
    try:
        assert storage.store_event(event)
        restored = storage.retrieve_events(AuditFilter())
        assert restored[0].timestamp == 1.0
        assert verify_integrity(restored, {event.event_id: event.calculate_hash()})
        assert verify_integrity(restored, {event.event_id: legacy_digest})
    finally:
        if isinstance(storage, ArrowAuditStorage):
            storage.close()


class _CaptureStorage:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def store_event(self, event: AuditEvent) -> bool:
        self.events.append(event)
        return True


def test_logging_helpers_keep_canonical_fields_ahead_of_caller_details() -> None:
    storage = _CaptureStorage()
    audit = AuditLogger(storage=storage, enable_real_time_alerts=False)  # type: ignore[arg-type]

    audit.log_risk_detection("risk-actual", "category-actual", "warning", "risk", [], {
        "risk_id": "risk-forged", "risk_category": "category-forged",
    })
    audit.log_mitigation_action("action-actual", "failed", "mitigation", {
        "action_id": "action-forged", "status": "completed",
    })
    audit.log_consensus_event("consensus-actual", "consensus", {
        "consensus_event_type": "consensus-forged",
    })
    audit.log_security_event("security-actual", "security", {
        "security_event_type": "security-forged",
    })
    audit.log_performance_event("metric-actual", 1.0, 2.0, "performance", {
        "metric_name": "metric-forged", "value": 100.0, "threshold": 0.0,
    })
    audit.log_user_action("user", "action-actual", "user action", {
        "action": "action-forged",
    })

    details = [event.details for event in storage.events]
    assert details[0]["risk_id"] == "risk-actual"
    assert details[0]["risk_category"] == "category-actual"
    assert details[1]["action_id"] == "action-actual"
    assert details[1]["status"] == "failed"
    assert details[2]["consensus_event_type"] == "consensus-actual"
    assert details[3]["security_event_type"] == "security-actual"
    assert details[4]["metric_name"] == "metric-actual"
    assert details[4]["value"] == 1.0
    assert details[4]["threshold"] == 2.0
    assert details[5]["action"] == "action-actual"


def test_integrity_query_distinguishes_unverified_and_verified_reads(tmp_path: Path) -> None:
    storage = FileAuditStorage(str(tmp_path))
    events = [_event("event-one", 1.0), _event("event-two", 2.0)]
    for event in events:
        assert storage.store_event(event)
    hashes = {event.event_id: event.calculate_hash() for event in events}

    unverified = AuditLogger(storage=storage, enable_real_time_alerts=False)
    result = unverified.query_events_with_integrity(AuditFilter(), limit=1)
    assert result.integrity_status is AuditIntegrityStatus.UNVERIFIED
    assert not result.is_verified
    assert len(result.events) == 1

    verified = AuditLogger(
        storage=storage,
        enable_real_time_alerts=False,
        integrity_digest_reader=lambda: hashes,
    )
    filtered = verified.query_events_with_integrity(
        AuditFilter(source_components=["test"]), limit=1,
    )
    assert filtered.integrity_status is AuditIntegrityStatus.VERIFIED
    assert filtered.is_verified
    assert len(filtered.events) == 1


def test_manifest_read_url_is_not_reused_from_write_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRC_ENV", "test")
    monkeypatch.setenv("HRC_AUDIT_MANIFEST_WRITE_URL", "postgresql://write-only")
    monkeypatch.setenv("HRC_AUDIT_MANIFEST_READ_URL", "postgresql://read-only")
    opened_urls: list[str] = []

    class ManifestStub:
        def __init__(self, url: str) -> None:
            opened_urls.append(url)

        def write_digest(self, _event_id: str, _digest: str) -> None:
            return None

        def load_hashes(self) -> dict[str, str]:
            return {}

    monkeypatch.setattr(audit_logger_module, "PostgresAuditManifest", ManifestStub)
    audit = AuditLogger(storage=FileAuditStorage(str(tmp_path)), enable_real_time_alerts=False)

    assert opened_urls == ["postgresql://write-only", "postgresql://read-only"]
    assert audit.integrity_digest_writer is not None
    assert audit.integrity_digest_reader is not None


@pytest.mark.parametrize("failure", ["archive_tamper", "manifest_error", "incomplete_manifest"])
def test_integrity_query_fails_closed_on_unverifiable_archive(
    tmp_path: Path, failure: str,
) -> None:
    storage = FileAuditStorage(str(tmp_path))
    event = _event("event-one", 1.0, "original")
    assert storage.store_event(event)
    hashes = {event.event_id: event.calculate_hash()}
    if failure == "archive_tamper":
        def reader() -> dict[str, str]:
            return hashes
        path = tmp_path / f"audit_{datetime.fromtimestamp(event.timestamp):%Y-%m-%d}.jsonl"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["description"] = "changed"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    elif failure == "manifest_error":
        def reader() -> dict[str, str]:
            raise OSError("manifest unavailable")
    else:
        def reader() -> dict[str, str]:
            return {**hashes, "missing-event": "0" * 64}

    audit = AuditLogger(
        storage=storage,
        enable_real_time_alerts=False,
        integrity_digest_reader=reader,
    )

    result = audit.query_events_with_integrity(AuditFilter())

    assert result.integrity_status is AuditIntegrityStatus.FAILED
    assert not result.is_verified
    assert result.events == []
