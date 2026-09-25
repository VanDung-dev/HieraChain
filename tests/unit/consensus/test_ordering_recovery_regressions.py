"""Regression tests for journal durability and fail-closed startup recovery."""

import asyncio
import threading
from types import SimpleNamespace

import pytest

import hierachain.error_mitigation.journal as journal_module
from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.recovery import OrderingRecovery
from hierachain.consensus.ordering.types import OrderingStatus


def test_async_journal_does_not_acknowledge_a_failed_disk_write(tmp_path, monkeypatch):
    """An event must not be accepted while its queued disk write can still fail."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        journal_module,
        "get_settings",
        lambda: SimpleNamespace(JOURNAL_FSYNC=False),
    )
    journal = journal_module.TransactionJournal(storage_dir="journal")
    write_started = threading.Event()
    finish_write = threading.Event()

    def failed_write(_event_data):
        write_started.set()
        finish_write.wait(timeout=0.1)
        return False

    monkeypatch.setattr(journal, "_write_event_to_file", failed_write)
    try:
        accepted = journal.log_event({"event_id": "evt-1"})
        assert write_started.wait(timeout=1), "background writer did not start"
        assert accepted is False, "journal acknowledged the event before its write failed"
    finally:
        finish_write.set()
        journal.flush()
        journal.close()


def test_replay_error_does_not_activate_ordering_service():
    class Journal:
        def replay(self):
            return iter([{"event_id": "evt-1", "channel_id": "channel-1"}])

    class Storage:
        def get_event_by_id(self, _event_id):
            raise OSError("storage unavailable during recovery")

    class BlockManager:
        async def check_timeout_block_creation(self):
            return None

    service = SimpleNamespace(
        journal=Journal(),
        blocks_created=0,
        storage_handler=SimpleNamespace(storage=Storage()),
        status=OrderingStatus.MAINTENANCE,
    )
    recovery_worker = SimpleNamespace(block_manager=BlockManager())
    recovery = OrderingRecovery(service, recovery_worker)
    processor = OrderingProcessor.__new__(OrderingProcessor)
    processor.service = service
    processor.recovery = recovery

    with pytest.raises(RuntimeError, match="recovery"):
        asyncio.run(processor._initialize_service())

    assert service.status is not OrderingStatus.ACTIVE
