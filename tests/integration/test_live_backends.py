"""Opt-in live checks for durable proofs and 2PC on fresh dedicated backends."""

import os
from pathlib import Path

import pytest

from hierachain.config.settings import settings
from hierachain.hierarchical import HierarchyManager, TransactionState


def _postgres_url() -> str:
    url = os.getenv("HRC_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("HRC_TEST_POSTGRES_URL is required for live backend checks")
    return url


def _close_hierarchy(hierarchy: HierarchyManager) -> None:
    for chain in hierarchy.sub_chains.values():
        chain.shutdown()
    close = getattr(hierarchy.storage, "close", None)
    if callable(close):
        close()


@pytest.fixture
def live_postgres(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = _postgres_url()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "postgres")
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.001)
    return url


def test_postgres_proof_ack_requires_saved_block(live_postgres: str) -> None:
    first = HierarchyManager("p1-proof-main")
    try:
        assert first.create_sub_chain("p1-proof-orders", "generic")
        subchain = first.get_sub_chain("p1-proof-orders")
        subchain.add_event({"entity_id": "proof-entity", "event": "created"})
        assert subchain.flush_pending_and_finalize(timeout=3.0) is not None
        proof_hash = subchain.get_latest_block().hash

        original_save = first.storage.save_block
        first.storage.save_block = lambda _block: False
        assert not first.submit_proof_to_main_chain("p1-proof-orders")
        assert first.main_chain.proof_count == 0
        assert not first.main_chain.verify_proof(proof_hash, "p1-proof-orders")

        first.storage.save_block = original_save
        assert first.submit_proof_to_main_chain("p1-proof-orders")
        assert first.main_chain.proof_count == 1
        anchor = first.main_chain.get_latest_block()
        saved = first.storage.get_block_by_index(anchor.index, first.main_chain.name)
        assert saved["hash"] == anchor.hash
        assert saved["signature"] == anchor.signature
        assert first.main_chain.verify_proof(proof_hash, "p1-proof-orders")
    finally:
        _close_hierarchy(first)

    restored = HierarchyManager("p1-proof-main")
    try:
        assert restored.main_chain.verify_proof(proof_hash, "p1-proof-orders")
        assert restored.main_chain.proof_count == 1
        assert restored.main_chain.get_latest_block().hash == anchor.hash
    finally:
        _close_hierarchy(restored)


def test_postgres_2pc_waits_for_both_durable_markers(live_postgres: str) -> None:
    first = HierarchyManager("p1-2pc-main")
    try:
        assert first.create_sub_chain("p1-2pc-source", "generic")
        assert first.create_sub_chain("p1-2pc-dest", "generic")
        source = first.get_sub_chain("p1-2pc-source")
        dest = first.get_sub_chain("p1-2pc-dest")
        source.register_entity("item-2pc", {"owner": "source"})
        dest.register_entity("item-2pc", {"owner": "dest"})

        original_complete = dest.complete_domain_operation
        dest.complete_domain_operation = lambda *_args, **_kwargs: True
        tx_id = first.initiate_cross_chain_transaction(
            source.name,
            dest.name,
            {"entity_id": "item-2pc", "operation_type": "transfer", "details": {}},
        )
        assert first.transaction_manager.get_transaction(tx_id).state is TransactionState.IN_DOUBT
        assert tx_id in dest.pending_transactions
        assert first.transaction_manager._read_latest_records()[tx_id]["phase"] == "commit"

        dest.complete_domain_operation = original_complete
        first.transaction_manager.retry_pending()
        assert first.transaction_manager.get_transaction(tx_id).state is TransactionState.COMMITTED
        assert first.transaction_manager._read_latest_records()[tx_id]["phase"] == "committed"
        for chain in (source, dest):
            markers = [
                record.get("transaction_step")
                for record in chain.ordering_service.journal.replay()
                if record.get("transaction_id") == tx_id
            ]
            assert markers.count("start") == 1
            assert markers.count("complete") == 1
            assert tx_id not in chain.pending_transactions
    finally:
        _close_hierarchy(first)

    restored = HierarchyManager("p1-2pc-main")
    try:
        assert restored.transaction_manager.get_transaction(tx_id).state is TransactionState.COMMITTED
    finally:
        _close_hierarchy(restored)


def test_redis_proof_fails_closed_and_2pc_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _postgres_url()
    port = os.getenv("HRC_TEST_REDIS_PORT")
    if not port:
        pytest.skip("HRC_TEST_REDIS_PORT is required for live Redis checks")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "redis")
    monkeypatch.setattr(settings, "DATABASE_URL", os.environ["HRC_TEST_POSTGRES_URL"])
    monkeypatch.setattr(settings, "REDIS_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "REDIS_PORT", int(port))
    monkeypatch.setattr(settings, "REDIS_DB", int(os.getenv("HRC_TEST_REDIS_DB", "15")))
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.001)

    hierarchy = HierarchyManager("p1-redis-main")
    try:
        assert hierarchy.create_sub_chain("p1-redis-orders", "generic")
        assert hierarchy.create_sub_chain("p1-redis-fulfillment", "generic")
        subchain = hierarchy.get_sub_chain("p1-redis-orders")
        destination = hierarchy.get_sub_chain("p1-redis-fulfillment")
        subchain.add_event({"entity_id": "redis-entity", "event": "created"})
        assert subchain.flush_pending_and_finalize(timeout=3.0) is not None
        assert not hierarchy.submit_proof_to_main_chain("p1-redis-orders")
        assert hierarchy.main_chain.proof_count == 0
        assert hierarchy.cross_level_sync.get_stats()["syncs_completed"] == 0

        subchain.register_entity("redis-item", {"owner": "orders"})
        destination.register_entity("redis-item", {"owner": "fulfillment"})
        tx_id = hierarchy.initiate_cross_chain_transaction(
            subchain.name,
            destination.name,
            {"entity_id": "redis-item", "operation_type": "transfer", "details": {}},
        )
        assert hierarchy.transaction_manager.get_transaction(tx_id).state is TransactionState.COMMITTED
    finally:
        _close_hierarchy(hierarchy)

    restored = HierarchyManager("p1-redis-main")
    try:
        assert restored.main_chain.proof_count == 0
        assert restored.transaction_manager.get_transaction(tx_id).state is TransactionState.COMMITTED
    finally:
        _close_hierarchy(restored)
