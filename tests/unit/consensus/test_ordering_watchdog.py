"""Regression coverage for ordering processor watchdog and commit offloading."""

import asyncio
import threading
from types import SimpleNamespace

from hierachain.consensus.ordering.block_manager import OrderingBlockManager
from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.types import OrderingStatus


def test_processing_thread_stops_supervisor_after_repeated_failures() -> None:
    class CrashingProcessor:
        async def run_async(self) -> None:
            raise RuntimeError("processor crashed")

    service = SimpleNamespace(
        config={"processor_max_restarts": 0},
        should_stop=threading.Event(),
        status=OrderingStatus.ACTIVE,
        processor=CrashingProcessor(),
        loop=None,
    )

    OrderingService._init_processing_thread(service)

    assert service.status is OrderingStatus.ERROR
    assert service.loop is not None and service.loop.is_closed()


def test_block_commit_runs_on_worker_thread() -> None:
    service = SimpleNamespace(
        should_stop=threading.Event(),
        _commit_lock=threading.RLock(),
        storage_handler=None,
        block_builder=None,
        metrics=None,
        journal=None,
        commit_queue=None,
        config={},
    )
    manager = OrderingBlockManager(service)
    main_thread = threading.get_ident()
    committed_on: list[int] = []

    def record(block: object) -> None:
        committed_on.append(threading.get_ident())

    manager.commit_block = record
    asyncio.run(
        manager.create_block_async(
            [{"entity_id": "e1", "event": "created", "timestamp": 1.0}]
        )
    )

    assert committed_on
    assert committed_on[0] != main_thread
