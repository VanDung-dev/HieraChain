"""WorldState must reflect the persisted chain throughout startup and recovery."""

from pathlib import Path

import pytest

from hierachain.config.settings import settings
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.state.world_state import WorldState


def _assert_projection_matches_history(chain: SubChain) -> None:
    expected = WorldState()
    for block in chain.chain:
        expected.apply_block(block)
    assert chain.world_state.get_all_states() == expected.get_all_states()
    assert chain.world_state.get_state_root() == expected.get_state_root()


@pytest.mark.parametrize("event_count", [0, 2])
def test_fresh_and_reopened_subchain_apply_genesis_once(
    isolated_chain_storage: None, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, event_count: int,
) -> None:
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.001)
    config = {"db_url": f"sqlite:///{tmp_path / 'projection.db'}"}
    chain = SubChain("projection", config=config)
    try:
        _assert_projection_matches_history(chain)
        genesis_id = chain.chain[0].to_event_list()[0]["entity_id"]
        assert chain.world_state.get_entity_state(genesis_id)["event_count"] == 1
        for index in range(event_count):
            chain.add_event({"entity_id": "entity", "event": f"update-{index}"})
            assert chain.flush_pending_and_finalize(timeout=3) is not None
        _assert_projection_matches_history(chain)
        snapshot = chain.world_state.get_all_states()
        chain.sync_chain()
        chain.sync_chain()
        assert chain.world_state.get_all_states() == snapshot
        hashes = [block.hash for block in chain.chain]
    finally:
        chain.shutdown()
    reopened = SubChain("projection", config=config)
    try:
        assert [block.hash for block in reopened.chain] == hashes
        _assert_projection_matches_history(reopened)
        assert reopened.world_state.get_all_states() == snapshot
        reopened.sync_chain()
        assert reopened.world_state.get_all_states() == snapshot
    finally:
        reopened.shutdown()
