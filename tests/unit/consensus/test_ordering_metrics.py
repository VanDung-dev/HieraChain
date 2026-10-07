"""Committed metrics must follow persisted block membership."""

import asyncio
import time
from pathlib import Path

import pytest

from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.types import (
    EventStatus,
    OrderingStatus,
    PendingEvent,
)


def test_commit_metrics_preserve_events_waiting_for_the_next_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(OrderingService, "_start_processing_thread", lambda self: None)
    service = OrderingService(config={
        "chain_name": "metrics", "db_url": "sqlite:///:memory:",
        "storage_dir": str(tmp_path / "data" / "journal"),
        "block_size": 2, "batch_size": 3, "batch_timeout": 60.0,
    })
    try:
        service.status = OrderingStatus.ACTIVE
        batch = [PendingEvent(
            event_id=f"event-{i}", channel_id="metrics", submitter_org="org",
            received_at=time.time(), status=EventStatus.PENDING,
            event_data={"event_id": f"event-{i}", "entity_id": f"entity-{i}",
                        "event": "created", "timestamp": time.time()},
        ) for i in range(3)]
        service.pending_events.update({event.event_id: event for event in batch})
        asyncio.run(service.processor.process_batch(batch))

        blocks = service.storage_handler.get_blocks_from_db(0)
        assert sum(len(block.events) for block in blocks) == 2
        assert service.metrics.get_stats()["events_committed"] == 2
        assert service.metrics.get_stats()["average_batch_size"] == 2
        assert list(service.storage_handler.processed_events) == ["event-2"]

        asyncio.run(service.processor.block_manager.check_timeout_block_creation(force=True))
        blocks = service.storage_handler.get_blocks_from_db(0)
        assert sum(len(block.events) for block in blocks) == 3
        assert service.metrics.get_stats()["events_committed"] == 3
        assert service.metrics.get_stats()["average_batch_size"] == 1.5
        assert not service.storage_handler.processed_events
    finally:
        service.shutdown()
