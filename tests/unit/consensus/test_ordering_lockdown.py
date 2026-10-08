"""Lockdown serializes commits and preserves pending durable work for resume."""

import asyncio
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.types import OrderingPausedError, OrderingStatus
from hierachain.core.block import Block


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[OrderingService]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(OrderingService, "_start_processing_thread", lambda self: None)
    instance = OrderingService({"db_url": f"sqlite:///{tmp_path / 'ordering.db'}",
                                "chain_name": "lockdown", "storage_dir": "lockdown-journal"})
    instance.status = OrderingStatus.ACTIVE
    yield instance
    instance.shutdown()


def _block() -> Block:
    return Block(0, [{"entity_id": "item", "event": "created", "timestamp": time.time()}])


def test_lockdown_blocks_commit_and_preserves_status(service: OrderingService) -> None:
    manager = service.processor.block_manager
    assert service.lockdown("regression")
    with pytest.raises(OrderingPausedError):
        manager.commit_block(_block())
    assert service.status is OrderingStatus.LOCKDOWN
    assert service.blocks_created == 0
    assert service.commit_queue.empty()
    assert service.storage_handler.storage.get_block_by_index(0, "lockdown") is None
    assert service.resume()
    manager.commit_block(_block())
    assert service.blocks_created == 1


def test_lockdown_waits_for_inflight_commit_and_blocks_following_commit(service: OrderingService) -> None:
    entered = threading.Event()
    release = threading.Event()
    lockdown_started = threading.Event()
    frozen = threading.Event()
    errors: list[Exception] = []
    def finalizer(block: Block, previous: Block | None) -> Block:
        entered.set()
        assert release.wait(2)
        return block
    service.block_finalizer = finalizer
    def commit() -> None:
        try:
            service.processor.block_manager.commit_block(_block())
        except Exception as exc:
            errors.append(exc)
    def freeze() -> None:
        lockdown_started.set()
        service.lockdown("in-flight regression")
        frozen.set()
    writer = threading.Thread(target=commit)
    freezer = threading.Thread(target=freeze)
    writer.start()
    try:
        assert entered.wait(2)
        freezer.start()
        assert lockdown_started.wait(2)
        assert not frozen.wait(0.1)
    finally:
        release.set()
        writer.join(2)
        if freezer.ident is not None:
            freezer.join(2)
    assert not errors
    assert frozen.is_set()
    assert service.blocks_created == 1
    with pytest.raises(OrderingPausedError):
        service.processor.block_manager.commit_block(_block())
    assert service.blocks_created == 1


def test_cut_batch_waits_for_resume_without_losing_events(service: OrderingService) -> None:
    events = _block().to_event_list()
    assert service.journal.log_event(events[0])
    assert service.lockdown("cut batch regression")
    async def exercise() -> None:
        task = asyncio.create_task(service.processor.block_manager.create_block_async(events))
        try:
            await asyncio.sleep(0.1)
            assert not task.done()
            assert service.blocks_created == 0
            assert service.resume()
            await asyncio.wait_for(task, timeout=2)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    asyncio.run(exercise())
    restored = service.storage_handler.get_blocks_from_db(0)
    assert restored[0].to_event_list() == events
    assert list(service.journal.replay())[0]["entity_id"] == "item"


def test_finalizer_cannot_lock_down_then_persist(service: OrderingService) -> None:
    def finalizer(block: Block, previous: Block | None) -> Block:
        service.lockdown("finalizer regression")
        return block
    service.block_finalizer = finalizer
    with pytest.raises(OrderingPausedError):
        service.processor.block_manager.commit_block(_block())
    assert service.status is OrderingStatus.LOCKDOWN
    assert service.blocks_created == 0


def test_recovery_completion_does_not_override_lockdown(service: OrderingService) -> None:
    async def recover() -> None:
        service.lockdown("during recovery")
    service.processor.recovery.recover_state_async = recover
    service.status = OrderingStatus.MAINTENANCE
    asyncio.run(service.processor._initialize_service())
    assert service.status is OrderingStatus.LOCKDOWN


def test_live_processor_preserves_queued_event_until_resume(service: OrderingService) -> None:
    collected = threading.Event()
    release = threading.Event()
    original_collect = service.processor._collect_next_event
    async def collect(batch: list) -> None:
        await original_collect(batch)
        if batch and not collected.is_set():
            collected.set()
            assert await asyncio.to_thread(release.wait, 3)
    service.processor._collect_next_event = collect
    service.processor.batch_size = 1
    service.block_builder.block_size = 1
    worker = threading.Thread(target=service._init_processing_thread)
    service.processing_thread = worker
    service.status = OrderingStatus.MAINTENANCE
    worker.start()
    try:
        assert service.wait_for_active(timeout=3)
        event_id = service.receive_event(
            {"entity_id": "queued-item", "event": "created", "timestamp": time.time()}, "c", "org",
        )
        assert collected.wait(3)
        assert service.lockdown("queued event regression")
        release.set()
        time.sleep(0.1)
        assert service.status is OrderingStatus.LOCKDOWN
        assert service.storage_handler.storage.get_block_by_index(0, "lockdown") is None
        assert service.resume()
        block = service.commit_queue.get(timeout=3)
        assert block.to_event_list()[0]["event_id"] == event_id
        assert service.storage_handler.get_blocks_from_db(0)[0].hash == block.hash
    finally:
        release.set()
        service.shutdown()


def test_shutdown_cannot_be_resumed_or_changed_to_lockdown(service: OrderingService) -> None:
    service.shutdown()
    assert not service.resume()
    assert not service.lockdown()
    assert service.status is OrderingStatus.SHUTDOWN
