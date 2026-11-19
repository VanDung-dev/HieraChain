"""Regression coverage for the logic-review technical-debt findings."""

from __future__ import annotations

import asyncio
import threading
import time
from queue import Queue
from types import SimpleNamespace

import pytest

from hierachain.adapters.database.base.sql_adapter import SQLBase
from hierachain.api.ledger.events import _build_event_data
from hierachain.api.ledger.schemas import EventRequest
from hierachain.consensus.ordering.block_manager import (
    OrderingBlockManager,
    _configured_block_spacing,
)
from hierachain.consensus.ordering.lifecycle import OrderingLifecycleMixin
from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.types import EventStatus, OrderingStatus
from hierachain.consensus.ordering.utils import generate_event_id
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
from hierachain.hierarchical.main_chain.base import MainChain
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.hierarchical.sub_chain.ordering import _check_divergence_and_rehydrate
from hierachain.hierarchical.sub_chain.proof import _update_local_state_after_proof


def _block(index: int, block_hash: str) -> SimpleNamespace:
    return SimpleNamespace(index=index, hash=block_hash)


def test_local_ahead_of_db_only_rehydrates_when_db_tip_disagrees() -> None:
    db_tip = _block(4, "db-hash")
    local_tip = _block(6, "local-hash")
    sub_chain = SimpleNamespace(
        name="orders",
        chain=[_block(3, "old"), db_tip, _block(5, "next"), local_tip],
    )

    assert _check_divergence_and_rehydrate(sub_chain, local_tip, db_tip) is False

    sub_chain.chain = [_block(4, "different"), local_tip]
    assert _check_divergence_and_rehydrate(sub_chain, local_tip, db_tip) is True


def test_api_retry_can_preserve_client_event_id_and_timestamp() -> None:
    request = EventRequest(
        entity_id="item",
        event_type="created",
        event_id="retry-key",
        timestamp=123.0,
        details={"value": "original"},
    )

    event = _build_event_data(request, {"value": "original"}, None, "user-1")

    assert event["event_id"] == "retry-key"
    assert event["timestamp"] == 123.0


def test_generated_event_ids_are_deterministic_per_payload() -> None:
    event = {"entity_id": "item", "event": "created", "timestamp": 1.5}

    first = generate_event_id(event, "orders")
    second = generate_event_id(dict(event), "orders")

    assert first == second
    assert generate_event_id(event, "payments") != first
    assert generate_event_id({**event, "timestamp": 2.5}, "orders") != first


def test_proof_submitted_event_id_is_stable_across_retries() -> None:
    captured: list[dict] = []
    sub_chain = SimpleNamespace(
        name="orders",
        last_proof_submission=0.0,
        last_proof_block_index=-1,
        add_event=captured.append,
    )
    block = SimpleNamespace(index=3, hash="a" * 64, timestamp=123.0)
    main_chain = SimpleNamespace(name="MainChain")

    _update_local_state_after_proof(sub_chain, main_chain, block, None)
    sub_chain.last_proof_block_index = -1
    _update_local_state_after_proof(sub_chain, main_chain, block, None)

    assert [event["event_id"] for event in captured] == [captured[0]["event_id"]] * 2
    assert captured[0]["event_id"] == f"proof-submitted:orders:3:{block.hash}"
    assert captured[0]["timestamp"] == block.timestamp
    assert captured[0]["details"]["submitted_at"] == block.timestamp


def test_watchdog_still_counts_failures_that_return_to_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hierachain.consensus.ordering import lifecycle as lifecycle_module

    attempts: list[int] = []

    class FlappingProcessor:
        async def run_async(self) -> None:
            attempts.append(len(attempts))
            _service.status = OrderingStatus.ACTIVE
            raise RuntimeError("active processor crashed")

    monkeypatch.setattr(
        lifecycle_module, "OrderingProcessor", lambda _service: FlappingProcessor()
    )
    _service = SimpleNamespace(
        config={"processor_max_restarts": 2},
        should_stop=threading.Event(),
        status=OrderingStatus.ACTIVE,
        processor=FlappingProcessor(),
        loop=None,
    )

    OrderingLifecycleMixin._init_processing_thread(_service)

    assert _service.status is OrderingStatus.ERROR
    assert len(attempts) == 3


def test_add_event_holds_chain_lock_while_publishing() -> None:
    lock_states: list[bool] = []

    def receive_event(*, event_data: dict, channel_id: str, submitter_org: str) -> str:
        lock_states.append(fake.lock._is_owned())
        return "event-1"

    fake = SimpleNamespace(
        name="orders",
        lock=threading.RLock(),
        pending_events=[],
        _PENDING_EVENTS_LIMIT=10,
        ordering_service=SimpleNamespace(receive_event=receive_event),
    )

    event_id = SubChain.add_event(fake, {"entity_id": "item", "event": "created"})

    assert event_id == "event-1"
    assert lock_states == [True]
    assert fake.pending_events[0]["event_id"] == "event-1"


def test_processed_batch_creates_blocks_in_event_order() -> None:
    processor = object.__new__(OrderingProcessor)
    processor.service = SimpleNamespace(pending_events={})
    processed: list[str] = []

    async def record(event: SimpleNamespace) -> None:
        await asyncio.sleep(0.01 if event.event_id == "1" else 0)
        processed.append(event.event_id)

    processor.process_single_event = record  # type: ignore[method-assign]
    batch = [
        SimpleNamespace(event_id="1", status=EventStatus.CERTIFIED),
        SimpleNamespace(event_id="2", status=EventStatus.CERTIFIED),
        SimpleNamespace(event_id="3", status=EventStatus.CERTIFIED),
    ]

    asyncio.run(processor._handle_processed_batch(batch))

    assert processed == ["1", "2", "3"]


def test_register_sub_chain_rolls_back_when_registration_event_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chain = MainChain(name="RollbackMainChain")

    def fail_add_event(_event: dict) -> str:
        raise ValueError("event append failed")

    monkeypatch.setattr(MainChain, "add_event", fail_add_event)

    assert chain.register_sub_chain("orders", {"domain_type": "sales"}) is False
    assert "orders" not in chain.registered_sub_chains
    assert "orders" not in chain.sub_chain_metadata
    assert "orders" not in chain.consensus.authorities


def test_event_type_query_uses_block_index_not_list_position() -> None:
    chain = Blockchain(name="IndexedChain")
    chain.chain.clear()
    chain.chain.append(Block(
        index=5,
        events=[{"entity_id": "item", "event": "created", "timestamp": 1.0}],
        previous_hash="0",
    ))
    chain._rebuild_event_indexes()

    events = chain.get_events_by_type("created")

    assert len(events) == 1
    assert events[0]["entity_id"] == "item"


def test_chain_type_uses_declared_kind_instead_of_class_name() -> None:
    assert SQLBase._determine_chain_type(SimpleNamespace(chain_kind="main")) == "main"
    assert SQLBase._determine_chain_type(SimpleNamespace(chain_kind="domain")) == "domain"
    assert SQLBase._determine_chain_type(SimpleNamespace(chain_kind="sub")) == "sub"
    assert SQLBase._determine_chain_type(SimpleNamespace()) == "sub"
    assert MainChain.chain_kind == "main"


def test_commit_queue_dequeue_marks_task_done() -> None:
    queue: Queue = Queue()
    service = SimpleNamespace(commit_queue=queue)
    queue.put("block")

    assert OrderingService.get_next_block(service) == "block"
    assert queue.unfinished_tasks == 0


def test_block_spacing_is_parsed_defensively() -> None:
    assert _configured_block_spacing({"block_spacing": 0.5}) == 0.5
    assert _configured_block_spacing({"block_spacing": "invalid"}) == 0.0
    assert _configured_block_spacing({}) == 0.0


def test_block_creation_waits_for_spacing_before_commit() -> None:
    committed_at: list[float] = []
    service = SimpleNamespace(
        should_stop=threading.Event(),
        _commit_lock=threading.RLock(),
        storage_handler=SimpleNamespace(last_block=SimpleNamespace(timestamp=time.time())),
        block_builder=None,
        metrics=None,
        journal=None,
        commit_queue=Queue(),
        config={"block_spacing": 0.05},
    )
    manager = OrderingBlockManager(service)
    manager.commit_block = lambda _block: committed_at.append(time.time())

    asyncio.run(manager.create_block_async(
        [{"entity_id": "item", "event": "created", "timestamp": time.time()}]
    ))

    assert committed_at
    assert committed_at[0] - service.storage_handler.last_block.timestamp >= 0.04
