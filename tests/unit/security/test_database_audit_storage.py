"""
Unit tests for persistent DatabaseAuditStorage.
"""

import os
import time
from pathlib import Path

import pytest

from hierachain.risk_management import audit_logger as audit_logger_module
from hierachain.risk_management.audit_logger import (
    ArrowAuditStorage,
    AuditEvent,
    AuditEventType,
    AuditFilter,
    AuditLogger,
    AuditSeverity,
    DatabaseAuditStorage,
    FileAuditStorage,
    verify_integrity,
)


@pytest.fixture
def temp_db_path(tmp_path):
    db_file = tmp_path / "test_audit.db"
    return str(db_file)


class TrustedManifestStub:
    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    def write(self, event_id: str, digest: str) -> None:
        self._hashes[event_id] = digest

    def read(self) -> dict[str, str]:
        return self._hashes.copy()


def test_database_audit_storage_init(temp_db_path):
    """Test that DatabaseAuditStorage initializes database and tables successfully."""
    DatabaseAuditStorage(temp_db_path)
    assert os.path.exists(temp_db_path)
    
    # Try creating connection to check table
    import sqlite3
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'")
    table = cursor.fetchone()
    conn.close()
    
    assert table is not None
    assert table[0] == "audit_events"


def test_store_and_retrieve_audit_events(temp_db_path):
    """Test storing and retrieving audit events persistently."""
    storage = DatabaseAuditStorage(temp_db_path)
    
    event = AuditEvent(
        event_id="test-event-123",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=time.time(),
        source_component="test_component",
        description="Test security event description",
        details={"user": "admin", "reason": "invalid_login"},
        ip_address="127.0.0.1"
    )
    
    # Store
    assert storage.store_event(event) is True
    
    # Retrieve
    filt = AuditFilter()
    events = storage.retrieve_events(filt)
    
    assert len(events) == 1
    retrieved = events[0]
    assert retrieved.event_id == event.event_id
    assert retrieved.event_type == event.event_type
    assert retrieved.severity == event.severity
    assert retrieved.description == event.description
    assert retrieved.details == event.details
    assert retrieved.ip_address == "127.0.0.1"


def test_audit_filter_severity_and_type(temp_db_path):
    """Test filtering by severity and event type."""
    storage = DatabaseAuditStorage(temp_db_path)
    
    e_ledger = AuditEvent(
        event_id="e_ledger",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.CRITICAL,
        timestamp=time.time() - 10,
        source_component="sys",
        description="critical sec",
        details={}
    )
    e_business = AuditEvent(
        event_id="e_business",
        event_type=AuditEventType.USER_ACTION,
        severity=AuditSeverity.INFO,
        timestamp=time.time(),
        source_component="web",
        description="info user",
        details={}
    )
    
    storage.store_event(e_ledger)
    storage.store_event(e_business)
    
    # Filter by CRITICAL severity
    f_crit = AuditFilter(severity_levels=[AuditSeverity.CRITICAL])
    results = storage.retrieve_events(f_crit)
    assert len(results) == 1
    assert results[0].event_id == "e_ledger"
    
    # Filter by USER_ACTION type
    f_type = AuditFilter(event_types=[AuditEventType.USER_ACTION])
    results = storage.retrieve_events(f_type)
    assert len(results) == 1
    assert results[0].event_id == "e_business"
    
    # Get count
    assert storage.get_event_count(f_crit) == 1
    assert storage.get_event_count(AuditFilter()) == 2


def test_database_audit_storage_cleanup(temp_db_path):
    """Test cleaning up old audit events from database."""
    storage = DatabaseAuditStorage(temp_db_path)
    now = time.time()
    
    old_event = AuditEvent(
        event_id="old-event",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=now - 100,
        source_component="test",
        description="old description",
        details={}
    )
    new_event = AuditEvent(
        event_id="new-event",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=now - 5,
        source_component="test",
        description="new description",
        details={}
    )
    
    storage.store_event(old_event)
    storage.store_event(new_event)
    
    # Cleanup events older than 50 seconds (should remove old_event)
    deleted = storage.cleanup_old_events(50)
    assert deleted == 1
    
    all_events = storage.retrieve_events(AuditFilter())
    assert len(all_events) == 1
    assert all_events[0].event_id == "new-event"


def test_database_audit_storage_concurrency(temp_db_path):
    """Test concurrent storage writes to DatabaseAuditStorage."""
    import threading
    storage = DatabaseAuditStorage(temp_db_path)
    
    def write_worker(worker_id):
        event = AuditEvent(
            event_id=f"concurrent-{worker_id}",
            event_type=AuditEventType.SYSTEM_EVENT,
            severity=AuditSeverity.INFO,
            timestamp=time.time(),
            source_component="thread",
            description=f"Worker {worker_id}",
            details={}
        )
        storage.store_event(event)
        
    threads = []
    for i in range(10):
        t = threading.Thread(target=write_worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    assert storage.get_event_count(AuditFilter()) == 10


def test_database_audit_storage_exception_handling(temp_db_path):
    """Test exception handling under database operation failures."""
    import sqlite3
    from unittest.mock import patch

    storage = DatabaseAuditStorage(temp_db_path)
    
    event = AuditEvent(
        event_id="test-fail",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=time.time(),
        source_component="test",
        description="test description",
        details={}
    )
    
    with patch("sqlite3.connect", side_effect=sqlite3.OperationalError("Mock database disk image is malformed")):
        # Should catch exception and return False safely without crashing
        assert storage.store_event(event) is False
        assert len(storage.retrieve_events(AuditFilter())) == 0
        assert storage.get_event_count(AuditFilter()) == 0
        assert storage.cleanup_old_events(10) == 0


def test_verify_integrity_requires_trusted_digests_and_detects_tampering():
    event = AuditEvent(
        event_id="integrity-event",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=1.0,
        source_component="test",
        description="original",
        details={"action": "login"},
    )
    expected_hashes = {event.event_id: event.calculate_hash()}

    assert not verify_integrity([event])
    assert verify_integrity([], {})
    assert verify_integrity([event], expected_hashes)

    event.details["action"] = "tampered"
    assert not verify_integrity([event], expected_hashes)
    assert not verify_integrity([event], {})
    assert not verify_integrity([event, event], expected_hashes)

    extra_event = AuditEvent(
        event_id="extra-integrity-event",
        event_type=AuditEventType.SYSTEM_EVENT,
        severity=AuditSeverity.INFO,
        timestamp=2.0,
        source_component="test",
        description="extra event",
        details={},
    )
    assert not verify_integrity([], expected_hashes)
    assert not verify_integrity([event, extra_event], expected_hashes)
    assert not verify_integrity(
        [event],
        {**expected_hashes, extra_event.event_id: extra_event.calculate_hash()},
    )


def test_audit_logger_captures_processed_event_digest_after_storage(
    tmp_path: Path,
) -> None:
    storage = FileAuditStorage(str(tmp_path))
    trusted_manifest = TrustedManifestStub()

    def capture_digest(event_id: str, digest: str) -> None:
        stored_events = storage.retrieve_events(AuditFilter())
        assert any(event.event_id == event_id for event in stored_events)
        trusted_manifest.write(event_id, digest)

    audit_logger = AuditLogger(
        storage=storage,
        enable_real_time_alerts=False,
        integrity_digest_writer=capture_digest,
    )
    audit_logger.add_event_processor(
        lambda event: AuditEvent.from_dict(
            {**event.to_dict(), "details": {**event.details, "processed": True}}
        )
    )

    audit_logger.log_security_event(
        event_type="login",
        description="Successful login",
        details={"user": "operator"},
    )

    stored_events = storage.retrieve_events(AuditFilter())
    assert len(stored_events) == 1
    assert stored_events[0].details["processed"] is True
    expected_hashes = trusted_manifest.read()
    assert expected_hashes[stored_events[0].event_id] == stored_events[0].calculate_hash()
    assert verify_integrity(stored_events, expected_hashes)


def test_audit_logger_surfaces_digest_writer_failure(tmp_path: Path) -> None:
    storage = FileAuditStorage(str(tmp_path))

    def fail_to_capture(_event_id: str, _digest: str) -> None:
        raise RuntimeError("manifest unavailable")

    audit_logger = AuditLogger(
        storage=storage,
        enable_real_time_alerts=False,
        integrity_digest_writer=fail_to_capture,
    )

    with pytest.raises(RuntimeError, match="manifest unavailable"):
        audit_logger.log_security_event(
            event_type="login",
            description="Successful login",
            details={"user": "operator"},
        )

    assert audit_logger.get_statistics()["total_events"] == 0
    assert len(storage.retrieve_events(AuditFilter())) == 1


def test_production_audit_logger_requires_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRC_ENV", "production")
    monkeypatch.delenv("HRC_AUDIT_MANIFEST_WRITE_URL", raising=False)

    with pytest.raises(RuntimeError, match="trusted digest manifest writer"):
        AuditLogger(storage=FileAuditStorage(str(tmp_path)))


def test_audit_logger_does_not_acknowledge_storage_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = FileAuditStorage(str(tmp_path))
    monkeypatch.setattr(storage, "store_event", lambda _event: False)
    audit_logger = AuditLogger(storage=storage, enable_real_time_alerts=False)

    with pytest.raises(RuntimeError, match="Failed to store audit event"):
        audit_logger.log_security_event("login", "Failed", {})
    assert audit_logger.get_statistics()["total_events"] == 0


def test_manifest_url_connects_default_digest_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import MagicMock

    backend = MagicMock()
    monkeypatch.setenv("HRC_ENV", "production")
    monkeypatch.setenv("HRC_AUDIT_MANIFEST_WRITE_URL", "postgresql://manifest-test")
    monkeypatch.setattr(
        audit_logger_module, "PostgresAuditManifest", lambda _url: backend,
    )
    storage = FileAuditStorage(str(tmp_path))
    audit_logger = AuditLogger(storage=storage, enable_real_time_alerts=False)

    audit_logger.log_security_event("login", "Successful", {"status": "ok"})

    event = storage.retrieve_events(AuditFilter())[0]
    backend.write_digest.assert_called_once_with(event.event_id, event.calculate_hash())
    assert audit_logger.get_statistics()["total_events"] == 1


def test_database_storage_integrity_manifest_accepts_valid_events(temp_db_path):
    storage = DatabaseAuditStorage(temp_db_path)
    event = AuditEvent(
        event_id="integrity-db-event",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=1.0,
        source_component="test",
        description="stored event",
        details={"action": "login"},
        affected_entities=["entity:1"],
    )
    expected_hashes = {event.event_id: event.calculate_hash()}

    assert storage.store_event(event)
    retrieved = storage.retrieve_events(AuditFilter())
    assert retrieved[0].affected_entities == ["entity:1"]
    assert verify_integrity(retrieved, expected_hashes)


def test_database_storage_adds_integrity_field_to_existing_schema(
    temp_db_path: str,
) -> None:
    import sqlite3

    conn = sqlite3.connect(temp_db_path)
    conn.execute(
        """
        CREATE TABLE audit_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            timestamp REAL NOT NULL,
            source_component TEXT NOT NULL,
            description TEXT NOT NULL,
            details TEXT,
            user_id TEXT,
            session_id TEXT,
            ip_address TEXT,
            correlation_id TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    storage = DatabaseAuditStorage(temp_db_path)
    event = AuditEvent(
        event_id="integrity-migrated-event",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=1.0,
        source_component="test",
        description="stored event",
        details={"action": "login"},
        affected_entities=["entity:1"],
    )
    expected_hashes = {event.event_id: event.calculate_hash()}

    assert storage.store_event(event)
    retrieved = storage.retrieve_events(AuditFilter())
    assert retrieved[0].affected_entities == ["entity:1"]
    assert verify_integrity(retrieved, expected_hashes)


def test_arrow_storage_integrity_manifest_covers_all_event_fields(tmp_path):
    storage = ArrowAuditStorage(str(tmp_path))
    event = AuditEvent(
        event_id="integrity-arrow-event",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.WARNING,
        timestamp=1.0,
        source_component="test",
        description="stored event",
        details={"action": "login"},
        affected_entities=["account:1"],
    )
    expected_hashes = {event.event_id: event.calculate_hash()}

    try:
        assert storage.store_event(event)
        retrieved = storage.retrieve_events(AuditFilter())
        assert retrieved[0].affected_entities == ["account:1"]
        assert verify_integrity(retrieved, expected_hashes)

        retrieved[0].details["action"] = "tampered"
        assert not verify_integrity(retrieved, expected_hashes)
    finally:
        storage.close()
