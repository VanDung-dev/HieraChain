"""Scenario tests for the audit logger."""

import shutil
import tempfile

import pytest

from hierachain.risk_management import (
    AuditEventType,
    AuditFilter,
    AuditLogger,
    AuditSeverity,
    FileAuditStorage,
)


@pytest.fixture
def audit_logger():
    temp_dir = tempfile.mkdtemp()
    try:
        yield AuditLogger(storage=FileAuditStorage(temp_dir))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_risk_detection_logging(audit_logger):
    audit_logger.log_risk_detection(
        "TEST_RISK_001", "consensus", "warning", "Test risk detected",
        ["consensus", "network"], {"test_param": "test_value"},
    )
    events = audit_logger.query_events(
        AuditFilter(event_types=[AuditEventType.RISK_DETECTED])
    )
    assert len(events) == 1
    assert events[0].severity == AuditSeverity.WARNING


def test_mitigation_action_logging(audit_logger):
    audit_logger.log_mitigation_action(
        "TEST_ACTION_001", "completed", "Test mitigation completed", {"duration": 30.5}
    )
    events = audit_logger.query_events(
        AuditFilter(event_types=[AuditEventType.MITIGATION_COMPLETED])
    )
    assert len(events) == 1
    assert events[0].details["action_id"] == "TEST_ACTION_001"


def test_security_event_logging(audit_logger):
    audit_logger.log_security_event(
        "authentication_failure", "Failed login attempt",
        {"username": "test_user", "attempts": 3},
        user_id="user_001", ip_address="192.168.1.100", severity="warning",
    )
    events = audit_logger.query_events(
        AuditFilter(event_types=[AuditEventType.SECURITY_EVENT])
    )
    assert len(events) == 1
    assert events[0].user_id == "user_001"


def test_performance_event_logging(audit_logger):
    audit_logger.log_performance_event(
        "cpu_usage", 85.5, 80.0, "CPU usage exceeded threshold", {"host": "node-01"}
    )
    events = audit_logger.query_events(
        AuditFilter(event_types=[AuditEventType.PERFORMANCE_EVENT])
    )
    assert len(events) == 1
    assert events[0].details["value"] == 85.5


def test_audit_event_filtering(audit_logger):
    audit_logger.log_risk_detection(
        "RISK_001", "consensus", "critical", "Critical risk", ["consensus"], {}
    )
    audit_logger.log_risk_detection(
        "RISK_002", "security", "warning", "Warning risk", ["security"], {}
    )
    events = audit_logger.query_events(
        AuditFilter(severity_levels=[AuditSeverity.CRITICAL])
    )
    assert len(events) == 1


def test_report_generation(audit_logger):
    audit_logger.log_risk_detection(
        "RISK_001", "consensus", "warning", "Test risk", ["consensus"], {}
    )
    report_filter = AuditFilter()
    assert audit_logger.generate_report(report_filter, "json").startswith("[")
    assert "event_id,event_type,severity" in audit_logger.generate_report(
        report_filter, "csv"
    )


def test_audit_statistics(audit_logger):
    audit_logger.log_risk_detection(
        "RISK_001", "consensus", "warning", "Test risk", ["consensus"], {}
    )
    audit_logger.log_mitigation_action("ACTION_001", "completed", "Test action", {})
    stats = audit_logger.get_statistics()
    assert stats["total_events"] == 2
    assert "risk_detected" in stats["events_by_type"]
    assert "mitigation_completed" in stats["events_by_type"]
