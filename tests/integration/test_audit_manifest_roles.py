"""Opt-in read/write role separation for an isolated, empty audit manifest."""

import os
import uuid

import psycopg
import pytest

from hierachain.adapters.database.audit_manifest import PostgresAuditManifest
from hierachain.risk_management.audit_logger import (
    AuditIntegrityStatus,
    AuditLogger,
    DatabaseAuditStorage,
)
from hierachain.risk_management.types import (
    AuditEvent,
    AuditEventType,
    AuditFilter,
    AuditSeverity,
)


@pytest.mark.integration
def test_verified_archive_uses_separate_manifest_roles(tmp_path) -> None:
    write_url = os.getenv("HRC_P2_TEST_MANIFEST_WRITE_URL")
    read_url = os.getenv("HRC_P2_TEST_MANIFEST_READ_URL")
    if not write_url or not read_url:
        pytest.skip("Provision an isolated empty manifest with separate test role URLs")
    writer = PostgresAuditManifest(write_url)
    reader = PostgresAuditManifest(read_url)
    assert reader.load_hashes() == {}, "This test requires its own empty manifest"
    storage = DatabaseAuditStorage(str(tmp_path / "archive.sqlite"))
    log = AuditLogger(storage=storage, integrity_digest_writer=writer.write_digest,
                      integrity_digest_reader=reader.load_hashes)
    event = AuditEvent(f"p2-{uuid.uuid4().hex}", AuditEventType.SYSTEM_EVENT, AuditSeverity.INFO,
                       1.0, "isolated-test", "accepted", {})
    log._log_event(event)
    result = log.query_events_with_integrity(AuditFilter())
    assert result.integrity_status is AuditIntegrityStatus.VERIFIED
    assert [entry.event_id for entry in result.events] == [event.event_id]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        writer.load_hashes()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        reader.write_digest("read-role-cannot-write", "0" * 64)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with psycopg.connect(write_url) as connection:
            connection.execute("DELETE FROM public.audit_event_digests")
    # The mutable archive can lose data, but verification must withhold results.
    import sqlite3

    with sqlite3.connect(storage.db_path) as connection:
        connection.execute("DELETE FROM audit_events")
    assert log.query_events_with_integrity(AuditFilter()).integrity_status is AuditIntegrityStatus.FAILED
