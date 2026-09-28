"""Focused regressions for cross-level sync and endorsement quorum handling."""

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.api.ledger.proofs import submit_proof
from hierachain.cluster.cross_level_sync import CrossLevelSyncManager
from hierachain.cluster.cross_level_sync_types import SyncResult
from hierachain.config.settings import settings
from hierachain.domains.chains.domain_chain import DomainChain
from hierachain.hierarchical.channel.channel import Channel
from hierachain.hierarchical.channel.policy import ChannelPolicy
from hierachain.hierarchical.channel.types import Organization
from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager
from hierachain.hierarchical.main_chain.base import MainChain
from hierachain.hierarchical.multi_org import create_organization as create_multi_org
from hierachain.hierarchical.private_data import PrivateCollection


class _ProofVerifier:
    def __init__(self, valid_proof: bytes):
        self.valid_proof = valid_proof

    def verify(self, proof: bytes, _public_inputs: dict[str, Any]) -> bool:
        return proof == self.valid_proof


def _real_chain_pair(
    storage_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    proof_verifier: _ProofVerifier | None = None,
) -> tuple[MainChain, DomainChain, CrossLevelSyncManager]:
    storage_dir.mkdir()
    monkeypatch.chdir(storage_dir)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.001)

    mainchain = MainChain("main")
    subchain = DomainChain("orders", "generic")
    assert subchain.connect_to_main_chain(mainchain)
    subchain.add_event({"entity_id": "entity-1", "event": "created"})
    assert subchain.flush_pending_and_finalize(timeout=2.0) is not None

    storage = SQLiteAdapter(database_path="main.db")
    assert storage.store_chain(mainchain)
    manager = CrossLevelSyncManager("node", proof_verifier=proof_verifier, storage=storage)
    manager.connect_mainchain(mainchain)
    manager.connect_subchain("orders", subchain)
    return mainchain, subchain, manager


def test_parent_blocks_are_not_copied_into_subchain_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mainchain, subchain, manager = _real_chain_pair(tmp_path / "raw", monkeypatch)
    try:
        mainchain.add_event({"entity_id": "global", "event": "root_update"})
        assert mainchain.finalize_block() is not None
        subchain_genesis = subchain.chain[0].hash
        subchain_height = len(subchain.chain)

        result = manager.sync_from_mainchain("orders")

        assert not result.success
        assert "unsupported" in result.error_message
        assert len(subchain.chain) == subchain_height
        assert subchain.chain[0].hash == subchain_genesis
        assert manager.get_stats()["blocks_synced_down"] == 0
        assert manager.get_stats()["syncs_completed"] == 0
        assert manager.get_stats()["syncs_failed"] == 1
    finally:
        subchain.shutdown()


def test_real_hierarchy_proof_submission_is_recorded_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    mainchain, subchain, sync = _real_chain_pair(tmp_path / "real", monkeypatch)
    manager = HierarchyManager.__new__(HierarchyManager)
    manager.sub_chains = {"orders": subchain}
    manager.main_chain = mainchain
    manager.cross_level_sync = sync
    try:
        block_hash = subchain.get_latest_block().hash

        assert manager.submit_proof_to_main_chain("orders")

        assert mainchain.proof_count == 1
        assert mainchain.verify_proof(block_hash, "orders")
        assert sync.get_stats()["syncs_completed"] == 1
        saved = sync.storage.get_block_by_index(mainchain.get_latest_block().index, mainchain.name)
        assert saved["hash"] == mainchain.get_latest_block().hash
        assert saved["signature"] == mainchain.get_latest_block().signature
    finally:
        subchain.shutdown()


def test_sync_waits_for_durable_block_and_retries_without_duplicate_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    mainchain, subchain, sync = _real_chain_pair(tmp_path / "retry", monkeypatch)
    storage = sync.storage
    original_save = storage.save_block
    storage.save_block = lambda _data: False
    try:
        failed = sync.sync_to_mainchain("orders")
        assert not failed.success
        assert sync.get_stats()["syncs_completed"] == 0
        assert subchain.last_proof_block_index == 0
        assert mainchain.proof_count == 0
        assert not mainchain.verify_proof(subchain.get_latest_block().hash, "orders")
        assert not sync.verify_cross_level_state("orders", "mainchain")
        assert mainchain.get_main_chain_stats()["total_proofs"] == 0

        storage.save_block = original_save
        recovered = sync.sync_to_mainchain("orders")
        assert recovered.success
        assert mainchain.proof_count == 1
        assert sum(
            event.get("event") == "proof_submission"
            for block in mainchain.chain for event in block.to_event_list()
        ) == 1
    finally:
        subchain.shutdown()


def test_direct_subchain_submission_rejects_missing_durable_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    mainchain, subchain, _sync = _real_chain_pair(tmp_path / "no-storage", monkeypatch)
    mainchain.proof_storage = None
    try:
        assert not subchain.submit_proof_to_main(mainchain)
        assert mainchain.proof_count == 0
        assert subchain.last_proof_block_index == 0
    finally:
        subchain.shutdown()


def test_mainchain_proof_survives_manager_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///hierarchy.db")
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.001)
    monkeypatch.setattr(
        HierarchyManager, "_create_storage",
        staticmethod(lambda: SQLiteAdapter(database_path="hierarchy.db")),
    )
    first = HierarchyManager()
    try:
        assert first.create_sub_chain("orders", "generic")
        subchain = first.get_sub_chain("orders")
        subchain.add_event({"entity_id": "entity-1", "event": "created"})
        assert subchain.flush_pending_and_finalize(timeout=2.0) is not None
        proof_hash = subchain.get_latest_block().hash
        assert first.submit_proof_to_main_chain("orders")
        main_hash = first.main_chain.get_latest_block().hash
    finally:
        for chain in first.sub_chains.values():
            chain.shutdown()

    restored = HierarchyManager()
    try:
        assert restored.main_chain.get_latest_block().hash == main_hash
        assert restored.main_chain.verify_proof(proof_hash, "orders")
    finally:
        for chain in restored.sub_chains.values():
            chain.shutdown()


def test_rest_proof_submission_records_once_through_cross_level_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    mainchain, subchain, sync = _real_chain_pair(tmp_path / "rest", monkeypatch)
    manager = HierarchyManager.__new__(HierarchyManager)
    manager.sub_chains = {"orders": subchain}
    manager.main_chain = mainchain
    manager.cross_level_sync = sync
    try:
        response = asyncio.run(submit_proof("orders", manager))

        assert response.success
        assert mainchain.proof_count == 1
        assert sync.get_stats()["syncs_completed"] == 1
    finally:
        subchain.shutdown()


def test_enabled_zk_proof_uses_the_subchain_state_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    storage_dir = tmp_path / "zk"
    storage_dir.mkdir()
    monkeypatch.chdir(storage_dir)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.001)
    subchain = DomainChain("orders", "generic")
    subchain.add_event({"entity_id": "entity-1", "event": "created"})
    assert subchain.flush_pending_and_finalize(timeout=2.0) is not None

    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", True)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", True)
    monkeypatch.setattr(settings, "ZK_MODE", "mock")
    mainchain = MainChain("main")
    assert subchain.connect_to_main_chain(mainchain)
    storage = SQLiteAdapter(database_path="main.db")
    assert storage.store_chain(mainchain)
    sync = CrossLevelSyncManager("node", storage=storage)
    sync.connect_mainchain(mainchain)
    sync.connect_subchain("orders", subchain)
    manager = HierarchyManager.__new__(HierarchyManager)
    manager.sub_chains = {"orders": subchain}
    manager.main_chain = mainchain
    manager.cross_level_sync = sync
    try:
        previous_block, latest_block = subchain.chain[-2:]

        assert manager.submit_proof_to_main_chain("orders")

        assert mainchain.proof_count == 1
        assert mainchain.recent_proofs[-1]["metadata"]["previous_merkle_root"] == (
            previous_block.merkle_root
        )
        assert mainchain.recent_proofs[-1]["metadata"]["latest_merkle_root"] == (
            latest_block.merkle_root
        )
        assert mainchain.recent_proofs[-1]["metadata"]["latest_block_index"] == (
            latest_block.index
        )
    finally:
        subchain.shutdown()


def test_precomputed_proof_requires_verifier_and_rejects_invalid_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ENABLE_ZK_PROOFS", False)
    monkeypatch.setattr(settings, "ZK_PROOF_REQUIRED_FOR_MAINCHAIN", False)
    mainchain, subchain, missing = _real_chain_pair(
        tmp_path / "missing", monkeypatch
    )
    try:
        result = missing.sync_to_mainchain("orders", b"valid")
        assert not result.success
        assert "No proof verifier" in result.error_message
        assert mainchain.proof_count == 0
    finally:
        subchain.shutdown()

    mainchain, subchain, manager = _real_chain_pair(
        tmp_path / "valid", monkeypatch, _ProofVerifier(b"valid")
    )
    try:
        invalid_result = manager.sync_to_mainchain("orders", b"invalid")
        assert not invalid_result.success
        assert manager.get_stats()["syncs_completed"] == 0
        assert manager.get_stats()["syncs_failed"] == 1
        assert mainchain.proof_count == 0

        valid_result = manager.sync_to_mainchain("orders", b"valid")
        assert valid_result.success
        assert mainchain.proof_count == 1
        assert mainchain.verify_proof(
            subchain.get_latest_block().hash, "orders"
        )
        assert manager.get_stats()["syncs_completed"] == 1
    finally:
        subchain.shutdown()


def test_hierarchy_manager_propagates_cross_level_sync_failure():
    manager = HierarchyManager.__new__(HierarchyManager)
    manager.sub_chains = {
        "subchain": SimpleNamespace(submit_proof_to_main=lambda _mainchain: True)
    }
    manager.main_chain = object()
    manager.cross_level_sync = SimpleNamespace(
        sync_to_mainchain=lambda _name: SyncResult(
            success=False, error_message="No proof verifier configured"
        )
    )

    assert not manager.submit_proof_to_main_chain("subchain")


def test_duplicate_endorsements_do_not_inflate_private_collection_quorum():
    collection = PrivateCollection(
        "private",
        {"org-a": object(), "org-b": object(), "org-c": object()},
        {"endorsement_policy": "MAJORITY"},
    )

    assert not collection._verify_endorsements(["org-a", "org-a"])
    assert not collection._verify_endorsements(["org-a", "org-a", "unknown"])
    assert collection._verify_endorsements(["org-a", "org-b"])


def test_duplicate_endorsements_do_not_inflate_channel_quorum():
    policy = ChannelPolicy({"endorsement": "MAJORITY"})

    assert not policy.evaluate_endorsement(["org-a", "org-a"], 2)
    assert policy.evaluate_endorsement(["org-a", "org-b"], 2)
    assert not policy.evaluate_endorsement(
        ["org-a", "org-b", "outsider"],
        2,
        eligible_org_ids={"org-a", "org-b"},
    )


def test_hierarchy_manager_channel_uses_registered_member_role_and_fails_closed():
    org_id = "org-membership"
    admin_user_id = "org-admin"
    member_user_id = "ordinary-member"
    org = create_multi_org(org_id, "Membership organization", [admin_user_id])
    org.register_member(
        member_user_id,
        {"user_id": member_user_id, "org_id": org_id, "role": "member"},
        "member",
    )
    org.members["foreign-user"] = {
        "identity": {
            "user_id": "foreign-user",
            "org_id": "another-org",
            "role": "admin",
        },
        "role": "admin",
    }

    manager = HierarchyManager.__new__(HierarchyManager)
    manager.organizations = {org_id: org}
    manager.channels = {}
    manager.storage = None
    manager._registry_lock = threading.RLock()
    channel = manager.create_channel("admin-only", [org_id])

    rejected_event = {"entity_id": "entity-1", "event": "member_write"}
    assert not channel.submit_event(rejected_event, org_id)
    assert not channel.submit_event(
        rejected_event, org_id, submitter_user_id="unknown-user"
    )
    assert not channel.submit_event(
        rejected_event, org_id, submitter_user_id=member_user_id
    )
    assert not channel.submit_event(
        rejected_event, org_id, submitter_user_id="foreign-user"
    )
    assert channel.ledger.current_block_events == []
    assert channel.event_statistics["total_events"] == 0
    assert channel.event_statistics["events_by_org"][org_id] == 0

    assert channel.submit_event(
        {"entity_id": "entity-2", "event": "admin_write"},
        org_id,
        submitter_user_id=admin_user_id,
    )
    assert len(channel.ledger.current_block_events) == 1
    assert channel.event_statistics["total_events"] == 1
    assert channel.event_statistics["events_by_org"][org_id] == 1

    member_channel = manager.create_channel(
        "member-write", [org_id], {"write": "MEMBER"}
    )
    assert not member_channel.submit_event(rejected_event, org_id)
    assert member_channel.submit_event(
        rejected_event, org_id, submitter_user_id=member_user_id
    )


def test_nonmember_endorsement_does_not_satisfy_channel_quorum():
    organizations = [
        Organization(
            org_id=org_id,
            name=org_id,
            msp_id=f"{org_id}-MSP",
            endpoints=[],
            certificates={},
            roles={"member"},
        )
        for org_id in ("org-a", "org-b", "org-c", "org-d")
    ]
    channel = Channel("quorum", organizations, {"endorsement": "MAJORITY"})

    assert not channel.suspend_channel(
        "maintenance", ["org-a", "org-b", "outsider"]
    )
