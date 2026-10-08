"""Regression coverage for proof-backed cross-level state verification."""

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
from hierachain.config.settings import settings
from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.hierarchical.hierarchy_manager import validation as validation_module
from hierachain.hierarchical.main_chain.base import MainChain
from hierachain.hierarchical.sub_chain.proof import _restore_proof_schedule


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
        # Proofs commit the latest block's event root, not the entity projection.
        assert result.state_root_after != subchain.world_state.get_state_root()
        assert sync.verify_cross_level_state("orders", "mainchain")
        mainchain.proof_index["orders"] = [999]
        assert sync.verify_cross_level_state("orders", "mainchain")

        subchain.get_latest_block().merkle_root = "f" * 64
        assert not sync.verify_cross_level_state("orders", "mainchain")
    finally:
        subchain.shutdown()


def test_cross_chain_report_degrades_for_missing_or_stale_due_proofs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ValidBlockVerifier:
        @staticmethod
        def verify_chain(_blocks, _trusted_keys):
            return SimpleNamespace(is_valid=True, message="valid")

    monkeypatch.setattr(
        validation_module, "get_block_verifier", lambda: _ValidBlockVerifier()
    )

    def report(latest_proof, *, due: bool):
        child = SimpleNamespace(
            chain=[object(), object()],
            trusted_public_keys={},
            is_chain_valid=lambda: True,
            get_latest_block=lambda: SimpleNamespace(index=1, hash="tip-hash"),
            should_submit_proof=lambda: due,
        )
        main = SimpleNamespace(
            chain=[object()],
            trusted_public_keys={},
            latest_proofs=({"orders": latest_proof} if latest_proof else {}),
            is_chain_valid=lambda: True,
        )
        manager = SimpleNamespace(main_chain=main, sub_chains={"orders": child})
        return validation_module._validate_cross_chain_consistency(manager)

    missing = report(None, due=True)
    assert not missing["overall_consistent"]
    assert missing["proof_consistency"]["orders"]["reason"].startswith(
        "No proof submitted"
    )

    stale_due = report(
        {"proof_hash": "previous-hash", "latest_block_index": 0}, due=True
    )
    assert not stale_due["overall_consistent"]
    assert not stale_due["proof_consistency"]["orders"]["consistent"]
    assert not stale_due["proof_consistency"]["orders"]["pending"]

    stale_not_due = report(
        {"proof_hash": "previous-hash", "latest_block_index": 0}, due=False
    )
    assert not stale_not_due["overall_consistent"]
    assert stale_not_due["proof_consistency"]["orders"]["pending"]
    assert not stale_not_due["proof_consistency"]["orders"]["consistent"]


def test_reconnect_restores_stale_proof_schedule_and_does_not_report_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ValidBlockVerifier:
        @staticmethod
        def verify_chain(_blocks, _trusted_keys):
            return SimpleNamespace(is_valid=True, message="valid")

    monkeypatch.setattr(
        validation_module, "get_block_verifier", lambda: _ValidBlockVerifier()
    )
    tip = SimpleNamespace(index=4, hash="current-tip")
    child = SimpleNamespace(
        name="orders",
        chain=[object()] * 5,
        trusted_public_keys={},
        last_proof_submission=10_000.0,
        last_proof_block_index=0,
        proof_submission_interval=60.0,
        get_latest_block=lambda: tip,
        is_chain_valid=lambda: True,
    )
    child.should_submit_proof = lambda: (
        time.time() - child.last_proof_submission >= child.proof_submission_interval
        and tip.index > child.last_proof_block_index
    )
    main = SimpleNamespace(
        name="main",
        chain=[object()],
        trusted_public_keys={},
        latest_proofs={
            "orders": {
                "proof_hash": "old-tip",
                "timestamp": time.time() - 120.0,
                "latest_block_index": 2,
            }
        },
        is_chain_valid=lambda: True,
    )

    assert _restore_proof_schedule(child, main)
    report = validation_module._validate_cross_chain_consistency(
        SimpleNamespace(main_chain=main, sub_chains={"orders": child})
    )

    assert child.should_submit_proof()
    assert not report["proof_consistency"]["orders"]["pending"]
    assert not report["proof_consistency"]["orders"]["consistent"]
    assert not report["overall_consistent"]


@pytest.mark.parametrize("timestamp,block_index", [
    ("unknown", None), (time.time() + 86_400, 1), (time.time() - 120, 4),
])
def test_invalid_restored_proof_schedule_is_conservatively_due(
    timestamp: str | float, block_index: int | None,
) -> None:
    child = SimpleNamespace(
        name="orders",
        last_proof_submission=time.time(),
        last_proof_block_index=0,
        get_latest_block=lambda: SimpleNamespace(index=3),
    )
    main = SimpleNamespace(
        latest_proofs={"orders": {"timestamp": timestamp, "latest_block_index": block_index}}
    )

    assert _restore_proof_schedule(child, main)
    assert child.last_proof_submission == 0.0
    assert child.last_proof_block_index == -1
