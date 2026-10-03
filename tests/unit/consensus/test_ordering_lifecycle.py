"""Queue cancellation and certification retention preserve durable outcomes."""

import asyncio
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.api.ledger.events import router
from hierachain.consensus.ordering.certifier import EventCertifier
from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.types import (
    EventStatus,
    OrderingBackpressureError,
    OrderingStatus,
    PendingEvent,
)
from hierachain.core.block import Block
from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.domains.chains.tx_manager import TransactionManager
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier


@pytest.fixture
def service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[OrderingService]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(OrderingService, "_start_processing_thread", lambda self: None)
    instance = OrderingService(
        {
            "db_url": f"sqlite:///{tmp_path / 'ordering.db'}",
            "chain_name": "p2",
            "storage_dir": "p2-journal",
            "enqueue_timeout": 0.1,
        }
    )
    instance.status = OrderingStatus.ACTIVE
    yield instance
    instance.shutdown()


def test_full_queue_rejects_before_journal_write(service: OrderingService) -> None:
    service.event_pool = Queue(maxsize=1)
    service.event_pool.put(object())
    with pytest.raises(OrderingBackpressureError) as error:
        service.receive_event(
            {"entity_id": "item", "event": "created", "timestamp": time.time()},
            "p2",
            "org",
        )
    assert error.value.journaled is False
    assert service.pending_events == {}
    assert service.journal.read_since()[0] == []


def test_authenticated_http_backpressure_reports_unjournaled_event(
    service: OrderingService,
) -> None:
    keys = KeyManager()
    key = keys.create_key(user_id="p2-user", permissions=["events"])
    verifier = APIKeyVerifier(
        {"enabled": True, "key_location": "header", "key_name": "x-api-key"}
    )
    verifier.key_manager = keys
    chain = SimpleNamespace(
        add_event=lambda event: service.receive_event(event, "p2", "org")
    )
    app = FastAPI()
    app.state.auth_verifier = verifier
    app.include_router(router)
    app.dependency_overrides[get_hierarchy_manager] = lambda: SimpleNamespace(
        get_sub_chain=lambda _: chain
    )
    service.event_pool = Queue(maxsize=1)
    service.event_pool.put(object())
    body = {
        "entity_id": "item",
        "event_type": "created",
        "sender": "a" * 64,
        "details": {},
    }
    with TestClient(app) as client:
        denied = client.post(
            "/chains/p2/events", json=body, headers={"x-api-key": "invalid"}
        )
        assert denied.status_code == 401
        overloaded = client.post(
            "/chains/p2/events", json=body, headers={"x-api-key": key}
        )
        assert overloaded.status_code == 503, overloaded.text
        assert overloaded.json()["detail"]["journaled"] is False
        assert overloaded.json()["detail"]["event_id"]
        assert service.pending_events == {}
        assert service.journal.read_since()[0] == []
        service.event_pool.get_nowait()
        accepted = client.post(
            "/chains/p2/events", json=body, headers={"x-api-key": key}
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["event_id"] in service.pending_events
    keys.key_cache.clear()
    keys.permission_cache.clear()


def test_shutdown_wakes_a_producer_waiting_for_capacity(
    service: OrderingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service.enqueue_timeout = 10
    service.event_pool = Queue(maxsize=1)
    service.event_pool.put(object())
    waiting = threading.Event()
    wait = service.event_pool.not_full.wait
    errors: list[Exception] = []

    def observed_wait(timeout: float) -> bool:
        waiting.set()
        return wait(timeout)

    def submit() -> None:
        try:
            service.receive_event(
                {"entity_id": "item", "event": "created"}, "p2", "org"
            )
        except Exception as exc:
            errors.append(exc)

    monkeypatch.setattr(service.event_pool.not_full, "wait", observed_wait)
    producer = threading.Thread(target=submit)
    producer.start()
    assert waiting.wait(1)
    service.shutdown()
    producer.join(timeout=1)
    assert not producer.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], OrderingBackpressureError)
    assert errors[0].journaled is False
    assert service.pending_events == {}


def test_durable_reconcile_retries_same_id_without_another_append(
    service: OrderingService,
) -> None:
    row = {
        "event_id": "durable-item",
        "channel_id": "p2",
        "entity_id": "item",
        "event": "created",
        "timestamp": time.time(),
    }
    assert service.journal.log_event(row)
    service.event_pool = Queue(maxsize=1)
    service.event_pool.put(object())
    with pytest.raises(OrderingBackpressureError) as error:
        service.reconcile_journal_event(row)
    assert error.value.journaled is True
    assert error.value.event_id == "durable-item"
    assert service.pending_events == {}
    service.event_pool.get_nowait()
    assert service.reconcile_journal_event(row) == "durable-item"
    assert service.event_pool.get_nowait().event_id == "durable-item"
    assert [event["event_id"] for event in service.journal.read_since()[0]] == [
        "durable-item"
    ]


def test_supplied_event_id_is_stable_and_payload_is_snapshotted(
    service: OrderingService,
) -> None:
    original = {
        "event_id": "stable-retry-id",
        "entity_id": "item",
        "event": "created",
        "details": {"items": ["one"]},
    }

    assert service.receive_event(original, "p2", "org") == "stable-retry-id"
    original["details"]["items"].append("caller-mutation")

    pending = service.pending_events["stable-retry-id"]
    assert pending.event_data["details"]["items"] == ["one"]
    assert service.receive_event(
        {
            "event_id": "stable-retry-id",
            "entity_id": "item",
            "event": "created",
            "details": {"items": ["one"]},
        },
        "p2",
        "org",
    ) == "stable-retry-id"
    assert service.event_pool.qsize() == 1
    assert [row["event_id"] for row in service.journal.read_since()[0]] == [
        "stable-retry-id"
    ]

    with pytest.raises(ValueError, match="already bound to different content"):
        service.receive_event(
            {
                "event_id": "stable-retry-id",
                "entity_id": "item",
                "event": "created",
                "details": {"items": ["different"]},
            },
            "p2",
            "org",
        )


def test_subchain_snapshots_nested_event_before_ordering_and_local_retention() -> None:
    chain = object.__new__(SubChain)
    chain.name = "p2"
    chain.pending_events = []
    chain.lock = threading.RLock()
    received: list[dict] = []

    def receive_event(event_data, channel_id, submitter_org):
        assert channel_id == "p2"
        assert submitter_org == "p2"
        received.append(event_data)
        return "subchain-stable-id"

    chain.ordering_service = SimpleNamespace(receive_event=receive_event)
    caller_event = {
        "event_id": "subchain-stable-id",
        "entity_id": "item",
        "event": "created",
        "timestamp": 1.0,
        "details": {"values": [1]},
    }

    assert chain.add_event(caller_event) == "subchain-stable-id"
    caller_event["details"]["values"].append(2)

    assert received[0]["details"]["values"] == [1]
    assert chain.pending_events[0]["details"]["values"] == [1]
    assert chain.pending_events[0]["event_id"] == "subchain-stable-id"


def test_stable_retry_requeues_matching_journal_content_without_second_append(
    service: OrderingService,
) -> None:
    row = {
        "event_id": "stable-after-ambiguous-ack",
        "channel_id": "p2",
        "entity_id": "item",
        "event": "created",
        "details": {"amount": 3},
        "timestamp": 1.0,
    }
    assert service.journal.log_event(row)

    assert service.receive_event(
        {
            "event_id": row["event_id"],
            "entity_id": "item",
            "event": "created",
            "details": {"amount": 3},
            "timestamp": 1.0,
        },
        "p2",
        "org",
    ) == row["event_id"]
    assert service.pending_events[row["event_id"]].event_data["details"] == {
        "amount": 3
    }
    assert service.event_pool.qsize() == 1
    assert [item["event_id"] for item in service.journal.read_since()[0]] == [
        row["event_id"]
    ]


def test_stable_id_conflicting_durable_content_is_rejected(
    service: OrderingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service.storage_handler.storage,
        "get_event_by_id",
        lambda _event_id: {
            "event_id": "durable-stable-id",
            "chain_name": "p2",
            "data": {
                "event_id": "durable-stable-id",
                "entity_id": "item",
                "event": "created",
                "details": {"value": "committed"},
            },
        },
    )
    with pytest.raises(ValueError, match="already bound to different content"):
        service.receive_event(
            {
                "event_id": "durable-stable-id",
                "entity_id": "item",
                "event": "created",
                "details": {"value": "conflict"},
            },
            "p2",
            "org",
        )
    assert service.event_pool.empty()
    assert service.journal.read_since()[0] == []


def test_concurrent_stable_retries_only_append_one_journal_record(
    service: OrderingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    both_checked = threading.Barrier(2)
    find_stable = service._find_stable_event

    def synchronized_find(event_id, channel_id, candidate):
        result = find_stable(event_id, channel_id, candidate)
        both_checked.wait(timeout=2)
        return result

    monkeypatch.setattr(service, "_find_stable_event", synchronized_find)
    results: list[str] = []
    errors: list[Exception] = []
    candidate = {
        "event_id": "concurrent-stable-id",
        "entity_id": "item",
        "event": "created",
        "details": {"value": 1},
    }

    def submit() -> None:
        try:
            results.append(service.receive_event(candidate, "p2", "org"))
        except Exception as error:
            errors.append(error)

    producers = [threading.Thread(target=submit) for _ in range(2)]
    for producer in producers:
        producer.start()
    for producer in producers:
        producer.join(timeout=3)

    assert all(not producer.is_alive() for producer in producers)
    assert not errors
    assert results == ["concurrent-stable-id", "concurrent-stable-id"]
    assert service.event_pool.qsize() == 1
    assert [row["event_id"] for row in service.journal.read_since()[0]] == [
        "concurrent-stable-id"
    ]


def test_rejected_results_do_not_remain_in_pending_or_grow_history(
    service: OrderingService,
) -> None:
    service.certifier = EventCertifier(max_history=8)
    service.processor.executor.certifier = service.certifier
    for index in range(32):
        event = PendingEvent(
            str(index),
            {"entity_id": "", "event": "created", "timestamp": time.time()},
            "p2",
            "org",
            time.time(),
            EventStatus.PENDING,
        )
        service.pending_events[event.event_id] = event
        asyncio.run(service.processor.process_single_event(event))
    assert not service.pending_events
    assert len(service.certifier.certified_events) == 8
    assert service.certifier.get_certification("0") is None
    assert service.get_event_status("31")["status"] == "rejected"


def test_evicted_certification_uses_persisted_event_status(
    service: OrderingService,
) -> None:
    block = Block(
        0,
        [
            {
                "event_id": "old-event",
                "entity_id": "item",
                "event": "created",
                "timestamp": time.time(),
            }
        ],
    )
    service.processor.block_manager.commit_block(block)
    service.certifier.certified_events.clear()
    assert service.get_event_status("old-event")["status"] == "ordered"
    assert service.get_event_status("missing") is None


def test_participant_tail_reads_new_markers_and_keeps_pending_on_missing_write(
    service: OrderingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for index in range(100):
        assert service.journal.log_event(
            {"entity_id": str(index), "event": "seed", "timestamp": time.time()}
        )
    chain = DomainChain.__new__(DomainChain)
    chain.name = "p2"
    chain.domain_type = "finance"
    chain.lock = threading.RLock()
    chain.pending_events = []
    chain.completed_operations = 0
    chain.entity_registry = {"item": {"status": "registered"}}
    chain.event_handlers = {}
    chain._domain_projection_healthy = True
    chain._domain_projection_errors = []
    chain._tx_manager = TransactionManager()
    chain._tx_commit_lock = threading.RLock()
    chain._transaction_event_markers = None
    chain.ordering_service = service
    chain.start_domain_operation = chain.start_operation
    chain.complete_domain_operation = chain.complete_operation
    assert chain._load_transaction_event_markers()
    original = service.journal.read_since
    counts: list[int] = []

    def observed(
        cursor: tuple[int, int] | None = None,
    ) -> tuple[list[dict], tuple[int, int]]:
        rows, next_cursor = original(cursor)
        counts.append(len(rows))
        return rows, next_cursor

    monkeypatch.setattr(service.journal, "read_since", observed)
    payload = {"entity_id": "item", "operation_type": "transfer", "details": {}}
    for index in range(3):
        tx_id = f"participant-{index}"
        chain._tx_manager.store_pending(tx_id, payload, is_source=True)
        assert chain.commit_transaction(tx_id)
    assert max(counts) == 2
    assert sum(counts) == 6
    assert len(service.pending_events) == 6
    monkeypatch.setattr(service.journal, "log_event", lambda _row: True)
    chain._tx_manager.store_pending("missing-write", payload, is_source=True)
    assert not chain.commit_transaction("missing-write")
    assert "missing-write" in chain._tx_manager.pending_transactions
    assert "missing-write" not in chain._tx_manager.committed_transactions
