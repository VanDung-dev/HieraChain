"""
Unit tests for persistent DatabaseAuditStorage.
"""

import time
import os
import pytest
from hierachain.risk_management.audit_logger import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditFilter,
    DatabaseAuditStorage,
)


@pytest.fixture
def temp_db_path(tmp_path):
    db_file = tmp_path / "test_audit.db"
    return str(db_file)


def test_database_audit_storage_init(temp_db_path):
    """Test that DatabaseAuditStorage initializes database and tables successfully."""
    storage = DatabaseAuditStorage(temp_db_path)
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
    from unittest.mock import patch
    import sqlite3
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

