"""Regression tests for journal durability and fail-closed startup recovery."""

import asyncio
import struct
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hierachain.consensus.ordering.service as service_module
import hierachain.error_mitigation.journal as journal_module
from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.recovery import OrderingRecovery
from hierachain.consensus.ordering.types import OrderingStatus
from hierachain.consensus.ordering.utils import make_serializable
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager
from hierachain.serialization import dumps_json, loads_json


@pytest.mark.parametrize(("timeout", "active"), [(None, True), (5.0, False)])
def test_wait_for_active_allows_long_replay_without_resetting_it(
    monkeypatch: pytest.MonkeyPatch, timeout: float | None, active: bool,
) -> None:
    service = object.__new__(service_module.OrderingService)
    service._commit_lock = threading.RLock()
    service.status = OrderingStatus.MAINTENANCE
    service.should_stop = threading.Event()
    service.processing_thread = SimpleNamespace(is_alive=lambda: True)
    now = [0.0]

    def advance(delay: float) -> None:
        now[0] += delay
        if now[0] >= 11:
            service.status = OrderingStatus.ACTIVE

    monkeypatch.setattr(service_module, "time", SimpleNamespace(monotonic=lambda: now[0], sleep=advance))
    assert service.wait_for_active(timeout=timeout) is active
    assert (now[0] >= 11) is active


@pytest.mark.parametrize("stopped", [False, True])
@pytest.mark.parametrize("status", [OrderingStatus.MAINTENANCE, OrderingStatus.ACTIVE])
def test_wait_for_active_stops_on_processor_failure_or_shutdown(stopped: bool, status: OrderingStatus) -> None:
    service = object.__new__(service_module.OrderingService)
    service._commit_lock = threading.RLock()
    service.status = status
    service.should_stop = threading.Event()
    if stopped:
        service.should_stop.set()
    service.processing_thread = SimpleNamespace(is_alive=lambda: stopped)
    assert service.wait_for_active(timeout=None) is False


def _event(event_id: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "entity_id": event_id,
        "event": "recovery_test",
        "timestamp": 1.0,
    }


def test_journal_does_not_acknowledge_a_failed_disk_write(tmp_path, monkeypatch):
    """An event must not be accepted when its journal write fails."""
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")

    def failed_write(_event_data):
        return False

    monkeypatch.setattr(journal, "_write_event_to_file", failed_write)
    try:
        assert journal.log_event({"event_id": "evt-1"}) is False
    finally:
        journal.close()


@pytest.mark.parametrize(("write_limit", "write_succeeds"), [(2, True), (0, False)])
def test_journal_handles_short_or_stalled_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_limit: int,
    write_succeeds: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")

    class PartialWriter:
        def __init__(self, handle: Any) -> None:
            self.handle = handle
            self.write_calls = 0

        def write(self, data: Any) -> int | None:
            self.write_calls += 1
            return self.handle.write(data[:write_limit])

        def flush(self) -> None:
            self.handle.flush()

        def fileno(self) -> int:
            return self.handle.fileno()

        def close(self) -> None:
            self.handle.close()

    partial_writer = PartialWriter(journal._journal_file)
    journal._journal_file = partial_writer

    try:
        assert journal.log_event(_event("evt-short-writes")) is write_succeeds
        if write_succeeds:
            assert partial_writer.write_calls > 2
        journal.close()

        restarted = journal_module.TransactionJournal(storage_dir="journal")
        try:
            expected = ["evt-short-writes"] if write_succeeds else []
            assert [event["event_id"] for event in restarted.replay()] == expected
        finally:
            restarted.close()
    finally:
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
        _commit_lock=threading.RLock(),
        should_stop=threading.Event(),
        journal=Journal(),
        blocks_created=0,
        storage_handler=SimpleNamespace(storage=Storage()),
        status=OrderingStatus.MAINTENANCE,
    )
    recovery_worker = SimpleNamespace(block_manager=BlockManager())
    recovery = OrderingRecovery(service, recovery_worker)
    processor = OrderingProcessor.__new__(OrderingProcessor)
    processor.service = service
    processor.should_stop = service.should_stop
    processor.recovery = recovery

    with pytest.raises(RuntimeError, match="recovery"):
        asyncio.run(processor._initialize_service())

    assert service.status is not OrderingStatus.ACTIVE


@pytest.mark.parametrize("torn_tail", [b"\x01\x02", struct.pack("<I", 16) + b"partial"])
def test_startup_repairs_torn_active_tail_and_future_appends_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, torn_tail: bytes
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")
    assert journal.log_event(_event("evt-before-crash"))
    active_file = journal.active_log_file
    journal.close()
    valid_size = active_file.stat().st_size
    with active_file.open("ab") as handle:
        handle.write(torn_tail)

    fsync_calls = []
    original_fsync = journal_module.os.fsync

    def track_fsync(fd):
        fsync_calls.append(fd)
        return original_fsync(fd)

    monkeypatch.setattr(journal_module.os, "fsync", track_fsync)
    repaired = journal_module.TransactionJournal(storage_dir="journal")
    assert active_file.stat().st_size == valid_size
    assert fsync_calls
    assert [event["event_id"] for event in repaired.replay()] == ["evt-before-crash"]
    assert repaired.log_event(_event("evt-after-repair"))
    repaired.close()

    restarted = journal_module.TransactionJournal(storage_dir="journal")
    try:
        assert [event["event_id"] for event in restarted.replay()] == [
            "evt-before-crash",
            "evt-after-repair",
        ]
    finally:
        restarted.close()


def test_oversized_active_frame_length_fails_without_reading_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")
    active_file = journal.active_log_file
    journal.close()
    active_file.write_bytes(struct.pack("<I", 0xFFFFFFFF))

    with pytest.raises(ValueError, match="exceeds maximum"):
        journal_module.TransactionJournal(storage_dir="journal")


def test_corrupt_complete_frame_keeps_ordering_in_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")
    journal.active_log_file.write_bytes(struct.pack("<I", 4) + b"nope")

    class Storage:
        def get_event_by_id(self, _event_id):
            return None

    class BlockManager:
        async def check_timeout_block_creation(self):
            return None

    service = SimpleNamespace(
        _commit_lock=threading.RLock(),
        should_stop=threading.Event(),
        journal=journal,
        blocks_created=0,
        storage_handler=SimpleNamespace(storage=Storage()),
        status=OrderingStatus.ACTIVE,
    )
    recovery = OrderingRecovery(service, SimpleNamespace(block_manager=BlockManager()))
    processor = OrderingProcessor.__new__(OrderingProcessor)
    processor.service = service
    processor.should_stop = service.should_stop
    processor.recovery = recovery

    with pytest.raises(ValueError, match="Corrupt Arrow batch"):
        asyncio.run(processor._initialize_service())

    assert service.status is OrderingStatus.MAINTENANCE
    journal.close()


def test_corrupt_rotated_arrow_journal_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")
    journal.close()
    rotated_file = journal.storage_path / "current_1.arrow"
    rotated_file.write_bytes(struct.pack("<I", 4) + b"nope")

    with pytest.raises(ValueError, match="Corrupt Arrow batch"):
        list(journal.replay())

    journal.close()


def test_active_journal_replays_after_older_rotated_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(journal_module, "_JOURNAL_MAX_FILE_SIZE", 1)
    journal = journal_module.TransactionJournal(
        storage_dir="transactions", active_log_name="cross_chain_2pc.arrow"
    )
    tx_id = "tx-rotation-order"
    try:
        assert journal.log_event({
            "entity_id": tx_id,
            "event": "cross_chain_2pc",
            "timestamp": 1.0,
            "tx_id": tx_id,
            "phase": "begin",
            "source_chain": "source",
            "destination_chain": "destination",
            "payload": {},
        })
        assert journal.log_event({
            "entity_id": tx_id,
            "event": "cross_chain_2pc",
            "timestamp": 2.0,
            "tx_id": tx_id,
            "phase": "commit",
            "source_chain": "source",
            "destination_chain": "destination",
            "payload": {},
        })

        manager = CrossChainTransactionManager(SimpleNamespace(), journal=journal)
        assert manager._phases[tx_id] == "commit"
    finally:
        journal.close()


def test_unreadable_legacy_parquet_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")
    journal.close()
    legacy_file = journal.storage_path / "current.parquet"
    legacy_file.write_bytes(b"PAR1not-a-valid-parquet-file")

    with pytest.raises(ValueError, match="legacy Parquet"):
        list(journal.replay())

    journal.close()


def test_replay_preserves_user_data_and_ids_for_jsonb_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")
    event_data = {
        "event_id": "evt-with-data",
        "channel_id": "payments",
        "entity_id": "account-1",
        "event": "transfer",
        "timestamp": 1.0,
        "data": {"amount": 25, "currency": "USD"},
    }
    try:
        assert journal.log_event(event_data)
        recovered = make_serializable(list(journal.replay())[0])

        assert recovered["event_id"] == event_data["event_id"]
        assert recovered["channel_id"] == event_data["channel_id"]
        assert recovered["data"] == event_data["data"]
        assert loads_json(dumps_json(recovered["data"])) == event_data["data"]
    finally:
        journal.close()


def test_replay_decodes_legacy_packed_extra_fields() -> None:
    row = {
        "entity_id": "account-1",
        "event": "transfer",
        "timestamp": 1.0,
        "details": [],
        "data": dumps_json({"event_id": "evt-legacy", "channel_id": "payments"}).encode("utf-8"),
    }

    recovered = journal_module._unpack_row_data(row)

    assert recovered["event_id"] == "evt-legacy"
    assert recovered["channel_id"] == "payments"
    assert recovered["data"] == {"event_id": "evt-legacy", "channel_id": "payments"}


def test_active_parquet_magic_is_quarantined_even_with_a_damaged_footer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    journal = journal_module.TransactionJournal(storage_dir="journal")
    active_file = journal.active_log_file
    journal.close()
    active_file.write_bytes(b"PAR1damaged-footer")

    reopened = journal_module.TransactionJournal(storage_dir="journal")
    try:
        assert active_file.exists()
        assert active_file.stat().st_size == 0
        with pytest.raises(ValueError, match="legacy Parquet"):
            list(reopened.replay())
    finally:
        reopened.close()
