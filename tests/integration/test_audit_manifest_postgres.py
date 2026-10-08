"""Opt-in audit manifest check against a provisioned PostgreSQL database."""

import hashlib
import os
import uuid

import psycopg
import pytest

from hierachain.adapters.database.audit_manifest import PostgresAuditManifest


@pytest.mark.integration
def test_postgres_audit_manifest_round_trip() -> None:
    database_url = os.getenv("HRC_TEST_AUDIT_MANIFEST_URL")
    if not database_url:
        pytest.skip("HRC_TEST_AUDIT_MANIFEST_URL is required")

    manifest = PostgresAuditManifest(database_url)
    event_id = f"test-{uuid.uuid4().hex}"
    digest = hashlib.sha256(event_id.encode()).hexdigest()

    manifest.write_digest(event_id, digest)
    assert manifest.load_hashes()[event_id] == digest
    with pytest.raises(psycopg.errors.UniqueViolation):
        manifest.write_digest(event_id, digest)
    with pytest.raises(ValueError, match="Invalid audit event ID or digest"):
        manifest.write_digest(event_id, "invalid")
