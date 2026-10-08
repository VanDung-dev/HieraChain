"""Bootstrap reuses one verified load and rebuilds every query index."""

from pathlib import Path

import pytest

import hierachain.hierarchical.sub_chain.base as subchain_module
from hierachain.config.settings import settings
from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.hierarchical.sub_chain.base import SubChain


def test_restart_preserves_event_queries_with_one_bootstrap_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.001)
    monkeypatch.setattr(subchain_module, "_consumer_loop", lambda _chain: None)
    loads: list[int] = []
    load = OrderingStorageHandler.get_blocks_from_db

    def observed_load(store: OrderingStorageHandler, start_index: int) -> list:
        loads.append(start_index)
        return load(store, start_index)

    monkeypatch.setattr(OrderingStorageHandler, "get_blocks_from_db", observed_load)
    config = {
        "db_url": f"sqlite:///{tmp_path / 'blocks.db'}",
        "block_size": 3,
        "batch_timeout": 0.1,
    }
    first = SubChain("p2_recovery", config=config)
    try:
        for index in range(3):
            first.add_event(
                {
                    "entity_id": f"item-{index}",
                    "event": "created",
                    "details": {"value": index},
                }
            )
        assert first.flush_pending_and_finalize(timeout=3) is not None
        expected = first.query_engine.get_events_by_type("created")
        assert len(expected) == 3
    finally:
        first.shutdown()

    loads.clear()
    restored = SubChain("p2_recovery", config=config)
    try:
        assert loads == [0]
        assert restored.query_engine.get_events_by_type("created") == expected
        assert restored.query_engine.get_events_by_type("missing") == []
        assert restored.query_engine.get_events_by_entity("item-1") == [expected[1]]
        assert restored.is_chain_valid()
        assert restored.ordering_service._bootstrap_blocks is None
        restored.sync_chain()
        assert loads == [0, 0]
        assert restored.query_engine.get_events_by_type("created") == expected
    finally:
        restored.shutdown()
