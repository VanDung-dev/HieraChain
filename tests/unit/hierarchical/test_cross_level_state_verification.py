"""Regression coverage for proof-backed cross-level state verification."""

from pathlib import Path

import pytest

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
from hierachain.config.settings import settings
from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.hierarchical.main_chain.base import MainChain


def test_state_verification_requires_committed_matching_merkle_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.001)
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)

    mainchain = MainChain("main")
    subchain = DomainChain("orders", "generic")
    assert subchain.connect_to_main_chain(mainchain)
    subchain.add_event({"entity_id": "entity-1", "event": "created"})
    assert subchain.flush_pending_and_finalize(timeout=2.0) is not None

    storage = SQLiteAdapter(database_path="main.db")
    assert storage.store_chain(mainchain)
    sync = CrossLevelSyncManager("node", storage=storage)
    sync.connect_mainchain(mainchain)
    sync.connect_subchain("orders", subchain)
    try:
        result = sync.sync_to_mainchain("orders")

        assert result.success
        assert result.state_root_after == subchain.get_latest_block().merkle_root
        assert sync.verify_cross_level_state("orders", "mainchain")
        mainchain.proof_index["orders"] = [999]
        assert sync.verify_cross_level_state("orders", "mainchain")

        subchain.get_latest_block().merkle_root = "f" * 64
        assert not sync.verify_cross_level_state("orders", "mainchain")
    finally:
        subchain.shutdown()
