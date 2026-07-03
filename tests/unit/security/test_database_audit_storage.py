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
    
    ev1 = AuditEvent(
        event_id="ev1",
        event_type=AuditEventType.SECURITY_EVENT,
        severity=AuditSeverity.CRITICAL,
        timestamp=time.time() - 10,
        source_component="sys",
        description="critical sec",
        details={}
    )
    ev2 = AuditEvent(
        event_id="ev2",
        event_type=AuditEventType.USER_ACTION,
        severity=AuditSeverity.INFO,
        timestamp=time.time(),
        source_component="web",
        description="info user",
        details={}
    )
    
    storage.store_event(ev1)
    storage.store_event(ev2)
    
    # Filter by CRITICAL severity
    f_crit = AuditFilter(severity_levels=[AuditSeverity.CRITICAL])
    results = storage.retrieve_events(f_crit)
    assert len(results) == 1
    assert results[0].event_id == "ev1"
    
    # Filter by USER_ACTION type
    f_type = AuditFilter(event_types=[AuditEventType.USER_ACTION])
    results = storage.retrieve_events(f_type)
    assert len(results) == 1
    assert results[0].event_id == "ev2"
    
    # Get count
    assert storage.get_event_count(f_crit) == 1
    assert storage.get_event_count(AuditFilter()) == 2
