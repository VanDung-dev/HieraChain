"""Deterministic tests for the HieraChain Docker runtime."""

import os
import shutil
import subprocess
import sys
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
    assert Path("/app/data").is_dir()
    assert Path("/app/log").is_dir()


def test_locked_runtime_dependencies_are_available() -> None:
    """The image contains the native dependencies used by the hot path."""
    assert pa.__version__
    assert orjson.loads(orjson.dumps({"ok": True})) == {"ok": True}


def test_journal_replays_after_process_crash() -> None:
    """An fsynced journal entry survives abrupt process termination."""
    storage_dir = Path("/app/data") / f"journal-test-{uuid.uuid4().hex}"
    event_id = f"docker-event-{uuid.uuid4().hex}"
    writer = """
import os
import sys
from hierachain.error_mitigation import TransactionJournal

journal = TransactionJournal(storage_dir=sys.argv[1], active_log_name="events.arrow")
if not journal.log_event({
    "event_id": sys.argv[2],
    "entity_id": "docker-test",
    "event": "created",
    "timestamp": 1.0,
}):
    os._exit(1)
os._exit(0)
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", writer, str(storage_dir), event_id],
            check=False,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")

        reopened = TransactionJournal(storage_dir=str(storage_dir), active_log_name="events.arrow")
        try:
            events = list(reopened.replay())
            assert [event["event_id"] for event in events] == [event_id]
        finally:
            reopened.close()
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)


def test_postgres_storage_is_reachable() -> None:
    """The Docker profile reaches the PostgreSQL service through the adapter."""
    handler = OrderingStorageHandler({"db_url": os.environ["DATABASE_URL"]})
    try:
        assert handler.storage.__class__.__name__ == "PostgresAdapter"
        assert handler.get_latest_block_from_db() is None
    finally:
        handler.close()
