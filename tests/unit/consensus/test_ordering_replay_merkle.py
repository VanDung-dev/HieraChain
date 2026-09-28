"""Regression coverage for journal replay block payload integrity."""

import asyncio
import threading
from queue import Queue
from typing import Any

import orjson

from hierachain.config.settings import settings
from hierachain.consensus.ordering.block_builder import BlockBuilder
from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.storage import _block_from_dict
from hierachain.consensus.ordering.types import OrderingStatus
from hierachain.security.identity_loader import (
    load_node_identity,
    load_trusted_block_keys,
)


class _Journal:
    def __init__(self, event: dict[str, Any]) -> None:
        self.event = event

    def replay(self) -> list[dict[str, Any]]:
        return [self.event]

    def log_event(self, _event: dict[str, Any]) -> bool:
        return True


class _Metrics:
    def record_certified(self) -> None:
        pass

    def record_rejected(self) -> None:
        pass

    def record_block_created(self, _event_count: int, _latency: float) -> None:
        pass


class _Certifier:
    def validate(
        self,
        _event: Any,
        *,
        allow_stale_timestamp: bool = False,
    ) -> dict[str, bool]:
        assert allow_stale_timestamp
        return {"valid": True}


class _PostgresLikeStorage:
    """Keep the database JSONB round-trip and run the normal block decoder."""

    def __init__(self) -> None:
        self.storage = self
        self.last_block = None
        self.processed_events = {}
        self.blocks = []

    def get_event_by_id(self, _event_id: str) -> None:
        return None

    def save_block(self, block: Any, _chain_name: str) -> tuple[int, float]:
        row = block.to_dict()
        row["events"] = orjson.loads(orjson.dumps(row["events"]))
        restored = _block_from_dict(row, load_trusted_block_keys(settings.BLOCK_TRUSTED_KEYS_FILE))
        self.blocks.append(restored)
        self.last_block = restored
        return len(row["events"]), 0.0


def test_journal_replay_block_payload_round_trips_with_postgres_jsonb() -> None:
    event = {
        "event_id": "replayed-event-1",
        "entity_id": "entity-1",
        "event": "record_created",
        "timestamp": 1.0,
        "details": {"source": "journal"},
        "data": {"value": 42, "unit": "items"},
    }
    storage = _PostgresLikeStorage()
    config = {"chain_name": "recovery-chain", "block_size": 1}
    service = type("Service", (), {})()
    service.should_stop = threading.Event()
    service.event_pool = Queue()
    service.pending_events = {}
    service.metrics = _Metrics()
    service.storage_handler = storage
    service.block_builder = BlockBuilder(config)
    service.certifier = _Certifier()
    service.config = config
    service.journal = _Journal(event)
    service.commit_queue = Queue()
    service.blocks_created = 0
    service.status = OrderingStatus.MAINTENANCE
    service.node_identity = load_node_identity()
    assert service.node_identity is not None

    processor = OrderingProcessor(service)
    asyncio.run(processor.recovery.recover_state_async())

    assert len(storage.blocks) == 1
    restored = storage.blocks[0]
    assert restored.to_event_list() == [event]
    assert restored.calculate_merkle_root() == restored.merkle_root
