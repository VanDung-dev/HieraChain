"""Deterministic tests for the HieraChain Docker runtime."""

import os
import shutil
import uuid
from pathlib import Path

import orjson
import pyarrow as pa
import pytest

from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.error_mitigation import TransactionJournal

pytestmark = pytest.mark.docker


def test_container_runtime_is_explicitly_configured() -> None:
    """The Docker test profile must use isolated, durable-safe settings."""
    assert os.getenv("HRC_ENV") == "test"
    assert os.getenv("HRC_STORAGE_BACKEND") == "postgres"
    assert os.getenv("DATABASE_URL", "").startswith("postgresql://")
    assert os.getenv("HRC_JOURNAL_FSYNC") == "true"
    assert Path("/app/data").is_dir()
    assert Path("/app/log").is_dir()


def test_locked_runtime_dependencies_are_available() -> None:
    """The image contains the native dependencies used by the hot path."""
    assert pa.__version__
    assert orjson.loads(orjson.dumps({"ok": True})) == {"ok": True}


def test_journal_replays_after_container_restart() -> None:
    """An append-only journal in the data volume survives a reopen."""
    storage_dir = Path("/app/data") / f"journal-test-{uuid.uuid4().hex}"
    journal = TransactionJournal(
        storage_dir=str(storage_dir),
        active_log_name="events.arrow",
    )
    try:
        assert journal.log_event(
            {
                "event_id": "docker-event-1",
                "entity_id": "docker-test",
                "event": "created",
                "timestamp": 1.0,
            }
        )
    finally:
        journal.close()

    reopened = TransactionJournal(
        storage_dir=str(storage_dir),
        active_log_name="events.arrow",
    )
    try:
        events = list(reopened.replay())
        assert [event["event_id"] for event in events] == ["docker-event-1"]
    finally:
        reopened.close()
        shutil.rmtree(storage_dir, ignore_errors=True)


def test_postgres_storage_is_reachable() -> None:
    """The Docker profile reaches the PostgreSQL service through the adapter."""
    handler = OrderingStorageHandler({"db_url": os.environ["DATABASE_URL"]})
    try:
        assert handler.storage.__class__.__name__ == "PostgresAdapter"
        assert handler.get_latest_block_from_db() is None
    finally:
        handler.close()
