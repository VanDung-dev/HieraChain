"""Fail-closed coverage for nested ordering recovery failures."""

import asyncio
import threading
import time
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest

import hierachain.consensus.ordering.certifier as certifier_module
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.consensus.ordering.block_builder import BlockBuilder
from hierachain.consensus.ordering.certifier import EventCertifier
from hierachain.consensus.ordering.metrics import OrderingMetrics
from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.consensus.ordering.types import (
    EventStatus,
    OrderingStatus,
    PendingEvent,
)
from hierachain.core.block import Block
from hierachain.security.identity_loader import load_node_identity
from hierachain.security.verify.block_verifier import sign_block


def _make_processor(
    tmp_path: Path,
    journal_events: list[dict[str, Any] | None],
    block_size: int = 1,
) -> tuple[SimpleNamespace, OrderingProcessor, OrderingStorageHandler]:
    config = {
        "db_url": f"sqlite:///{tmp_path / 'ordering.db'}",
        "chain_name": "test-chain",
        "batch_size": 1,
        "block_size": block_size,
        "batch_timeout": 0.1,
    }
    storage_handler = OrderingStorageHandler(config)
    identity = load_node_identity()
    assert identity is not None, "Test signer must be configured"
    service = SimpleNamespace(
        node_identity=identity,
        should_stop=threading.Event(),
        event_pool=Queue(),
        pending_events={},
        metrics=OrderingMetrics(),
        storage_handler=storage_handler,
        block_builder=BlockBuilder(config),
        certifier=EventCertifier(),
        config=config,
        journal=SimpleNamespace(
            replay=lambda: iter(journal_events),
            log_event=lambda _event: True,
        ),
        commit_queue=Queue(),
        blocks_created=0,
        status=OrderingStatus.MAINTENANCE,
    )
    return service, OrderingProcessor(service), storage_handler


def _journal_event() -> dict[str, Any]:
    return {
        "event_id": "event-1",
        "channel_id": "channel-1",
        "entity_id": "entity-1",
        "event": "created",
        "timestamp": 1.0,
    }


def test_save_block_failure_during_replay_keeps_service_in_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, processor, storage_handler = _make_processor(
        tmp_path, [_journal_event()]
    )
    monkeypatch.setattr(storage_handler.storage, "save_block", lambda _data: False)

    with pytest.raises(RuntimeError, match="Journal recovery failed for event event-1") as exc:
        asyncio.run(processor._initialize_service())

    assert isinstance(exc.value.__cause__, RuntimeError)
    assert "Storage adapter rejected block 0" in str(exc.value.__cause__)
    assert service.status is OrderingStatus.MAINTENANCE
    assert service.blocks_created == 0
    assert service.commit_queue.empty()


def test_final_recovery_flush_failure_keeps_service_in_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, processor, storage_handler = _make_processor(
        tmp_path, [_journal_event()], block_size=2
    )
    monkeypatch.setattr(storage_handler.storage, "save_block", lambda _data: False)

    with pytest.raises(RuntimeError, match="Storage adapter rejected block 0"):
        asyncio.run(processor._initialize_service())

    assert service.status is OrderingStatus.MAINTENANCE
    assert service.blocks_created == 0
    assert service.commit_queue.empty()


def test_stale_journal_event_is_persisted_before_service_activates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_data = _journal_event()
    event_data["timestamp"] = time.time() - 301
    service, processor, storage_handler = _make_processor(
        tmp_path, [event_data], block_size=2
    )
    save_observations: list[tuple[OrderingStatus, bool]] = []
    save_block = storage_handler.save_block

    def observe_save(block: Block, chain_name: str | None) -> tuple[int, float]:
        result = save_block(block, chain_name)
        event_persisted = (
            storage_handler.storage.get_event_by_id("event-1") is not None
        )
        save_observations.append((service.status, event_persisted))
        return result

    monkeypatch.setattr(storage_handler, "save_block", observe_save)

    asyncio.run(processor._initialize_service())

    assert save_observations == [(OrderingStatus.MAINTENANCE, True)]
    assert storage_handler.get_latest_block_from_db() is not None
    assert service.status is OrderingStatus.ACTIVE


def test_database_read_failure_during_replay_keeps_service_in_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, processor, storage_handler = _make_processor(
        tmp_path, [_journal_event()]
    )

    def unavailable_connection() -> NoReturn:
        raise OSError("database unavailable")

    monkeypatch.setattr(
        storage_handler.storage, "_get_connection", unavailable_connection
    )

    with pytest.raises(RuntimeError, match="Journal recovery failed for event event-1") as exc:
        asyncio.run(processor._initialize_service())

    assert isinstance(exc.value.__cause__, OSError)
    assert service.status is OrderingStatus.MAINTENANCE


def test_certification_failure_during_replay_keeps_service_in_maintenance(
    tmp_path: Path,
) -> None:
    service, processor, _storage_handler = _make_processor(
        tmp_path, [_journal_event()]
    )

    def failed_certification(
        _event: PendingEvent, *, allow_stale_timestamp: bool = False
    ) -> dict[str, bool]:
        raise OSError("certifier unavailable")

    service.certifier.validate = failed_certification

    with pytest.raises(RuntimeError, match="Journal recovery failed for event event-1") as exc:
        asyncio.run(processor._initialize_service())

    assert isinstance(exc.value.__cause__, OSError)
    assert service.status is OrderingStatus.MAINTENANCE


def test_rejected_event_during_replay_keeps_service_in_maintenance(
    tmp_path: Path,
) -> None:
    service, processor, storage_handler = _make_processor(
        tmp_path, [_journal_event()]
    )
    service.certifier.validate = lambda *_args, **_kwargs: {
        "valid": False,
        "validation_errors": ["invalid signature"],
    }

    with pytest.raises(
        RuntimeError, match="Journal recovery failed for event event-1"
    ) as exc:
        asyncio.run(processor._initialize_service())

    assert isinstance(exc.value.__cause__, ValueError)
    assert "Replay rejected event event-1" in str(exc.value.__cause__)
    assert service.status is OrderingStatus.MAINTENANCE
    assert storage_handler.storage.get_event_by_id("event-1") is None


def test_get_latest_block_database_failure_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SQLiteAdapter(str(tmp_path / "ordering.db"))

    def unavailable_connection() -> NoReturn:
        raise OSError("database unavailable")

    monkeypatch.setattr(adapter, "_get_connection", unavailable_connection)

    with pytest.raises(OSError, match="database unavailable"):
        adapter.get_latest_block(chain_name="test-chain")


def test_load_from_db_propagates_failure_on_nonterminal_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _processor, storage_handler = _make_processor(tmp_path, [])
    previous_hash = "0"
    for index in range(3):
        block = Block(
            index=index,
            events=[
                {
                    "event_id": f"stored-event-{index}",
                    "entity_id": "entity-1",
                    "event": "created",
                    "timestamp": float(index + 1),
                }
            ],
            previous_hash=previous_hash,
        )
        sign_block(block, service.node_identity.node_id, service.node_identity.signing_keypair)
        storage_handler.save_block(block, "test-chain")
        previous_hash = block.hash
    execute_lookup = storage_handler.storage._execute_get_block_by_index

    def fail_after_first_block(
        cursor: Any, index: int, chain_name: str | None
    ) -> dict[str, Any] | None:
        if index == 1:
            raise OSError("database unavailable at block 1")
        return execute_lookup(cursor, index, chain_name)

    monkeypatch.setattr(
        storage_handler.storage, "_execute_get_block_by_index", fail_after_first_block
    )

    with pytest.raises(OSError, match="database unavailable at block 1"):
        storage_handler.get_blocks_from_db(0)


def test_list_chains_returns_sorted_subchain_metadata(tmp_path: Path) -> None:
    _service, _processor, storage_handler = _make_processor(tmp_path, [])
    with storage_handler.storage._get_connection() as conn:
        conn.executemany(
            "INSERT INTO chains (name, chain_type, domain_type, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("z-chain", "sub", "retail", 1.0, 1.0),
                ("a-chain", "sub", "finance", 1.0, 1.0),
                ("main-chain", "main", None, 1.0, 1.0),
            ],
        )
        conn.commit()

    assert storage_handler.storage.list_chains() == [
        {"name": "a-chain", "chain_type": "sub", "domain_type": "finance"},
        {"name": "z-chain", "chain_type": "sub", "domain_type": "retail"},
    ]


def test_list_chains_database_failure_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SQLiteAdapter(str(tmp_path / "ordering.db"))

    def unavailable_connection() -> NoReturn:
        raise OSError("database unavailable")

    monkeypatch.setattr(adapter, "_get_connection", unavailable_connection)

    with pytest.raises(OSError, match="database unavailable"):
        adapter.list_chains()


def test_runtime_processing_failure_stops_without_retrying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, processor, storage_handler = _make_processor(tmp_path, [])
    event_data = _journal_event()
    event_data["timestamp"] = time.time()
    pending_event = PendingEvent(
        event_id="event-1",
        event_data=event_data,
        channel_id="channel-1",
        submitter_org="test",
        received_at=1.0,
        status=EventStatus.PENDING,
    )
    service.event_pool.put(pending_event)
    failed_saves = 0

    def reject_save(_data: dict[str, Any]) -> bool:
        nonlocal failed_saves
        failed_saves += 1
        return False

    monkeypatch.setattr(storage_handler.storage, "save_block", reject_save)

    with pytest.raises(RuntimeError, match="Storage adapter rejected block"):
        asyncio.run(processor.run_async())

    assert failed_saves == 1
    assert service.status is OrderingStatus.MAINTENANCE


def test_null_journal_entry_fails_closed(tmp_path: Path) -> None:
    service, processor, _storage_handler = _make_processor(tmp_path, [None])

    with pytest.raises(RuntimeError, match="Journal recovery failed for event unknown") as exc:
        asyncio.run(processor._initialize_service())

    assert isinstance(exc.value.__cause__, ValueError)
    assert service.status is OrderingStatus.MAINTENANCE


def test_runtime_stale_event_is_rejected(tmp_path: Path) -> None:
    service, processor, storage_handler = _make_processor(tmp_path, [])
    event_data = _journal_event()
    event_data["timestamp"] = time.time() - 301
    pending_event = PendingEvent(
        event_id="event-1",
        event_data=event_data,
        channel_id="channel-1",
        submitter_org="client",
        received_at=time.time(),
        status=EventStatus.PENDING,
    )
    service.status = OrderingStatus.ACTIVE

    asyncio.run(processor.process_single_event(pending_event))

    assert pending_event.status is EventStatus.REJECTED
    assert service.status is OrderingStatus.ACTIVE
    assert storage_handler.storage.get_event_by_id("event-1") is None


def test_replay_timestamp_override_still_rejects_future_and_nonfinite_values() -> None:
    for index, timestamp in enumerate((time.time() + 301, float("inf"), float("nan"))):
        event_data = _journal_event()
        event_data["event_id"] = f"event-{index}"
        event_data["timestamp"] = timestamp
        pending_event = PendingEvent(
            event_id=event_data["event_id"],
            event_data=event_data,
            channel_id="channel-1",
            submitter_org="recovery",
            received_at=time.time(),
            status=EventStatus.PENDING,
        )

        result = EventCertifier().validate(
            pending_event, allow_stale_timestamp=True
        )

        assert result["valid"] is False


def test_stale_replay_still_runs_signature_and_required_zk_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_data = _journal_event()
    event_data.update(
        {
            "timestamp": time.time() - 301,
            "sender": "public-key",
            "signature": "signature",
            "details": {"payload": "signed-payload"},
            "zk_proof": "proof",
        }
    )
    pending_event = PendingEvent(
        event_id="event-1",
        event_data=event_data,
        channel_id="channel-1",
        submitter_org="recovery",
        received_at=time.time(),
        status=EventStatus.PENDING,
    )
    checks: list[str] = []

    def check_signature(_event: PendingEvent, _certification: dict[str, Any]) -> None:
        checks.append("signature")

    def check_zk_proof(_event: PendingEvent) -> dict[str, Any]:
        checks.append("zk")
        return {"verified": False, "required": True, "reason": "invalid proof"}

    monkeypatch.setattr(certifier_module, "verify_event_signature", check_signature)
    monkeypatch.setattr(certifier_module, "_verify_zk_proof", check_zk_proof)
    monkeypatch.setattr(certifier_module.settings, "ENABLE_ZK_PROOFS", True)
    monkeypatch.setattr(
        certifier_module.settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", True
    )

    result = EventCertifier().validate(
        pending_event, allow_stale_timestamp=True
    )

    assert checks == ["signature", "zk"]
    assert result["valid"] is False
    assert result["validation_errors"] == [
        "ZK proof verification failed: invalid proof"
    ]
