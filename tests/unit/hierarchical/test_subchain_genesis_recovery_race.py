"""Regression coverage for SubChain journal replay and queue rehydration."""

import time
from pathlib import Path

import pytest

from hierachain.consensus.ordering.certifier import EventCertifier
from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.types import OrderingStatus, PendingEvent
from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.core.block import Block
from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.hierarchical.sub_chain import base as sub_chain_base
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.security.verify.block_verifier import sign_block


def test_journal_replay_rehydrates_once_and_rejects_before_persisting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sub_chain_base.settings, "BLOCK_INTERVAL", 0.02)
    chain_name = "genesis_recovery_race"
    journal_dir = tmp_path / "data" / chain_name / "journal"
    journal_dir.mkdir(parents=True)
    journal = TransactionJournal(
        storage_dir=str(journal_dir),
        active_log_name=f"node_{chain_name}_orderer_journal.arrow",
    )
    try:
        assert journal.log_event(
            {
                "event_id": "replay-after-genesis",
                "entity_id": "recovery-test",
                "event": "replayed_event",
                "timestamp": time.time() - 60,
                "channel_id": chain_name,
            }
        )
    finally:
        journal.close()

    def accept_replayed_event(
        _self: EventCertifier,
        event: PendingEvent,
        *,
        allow_stale_timestamp: bool = False,
    ) -> dict[str, object]:
        assert allow_stale_timestamp
        return {"event_id": event.event_id, "valid": True, "validation_errors": []}

    monkeypatch.setattr(EventCertifier, "validate", accept_replayed_event)
    monkeypatch.setattr(sub_chain_base, "_consumer_loop", lambda _chain: None)
    chain = SubChain(
        chain_name,
        config={
            "db_url": f"sqlite:///{tmp_path / 'chain.db'}",
            "storage_dir": str(journal_dir),
            "block_size": 1,
        },
    )
    try:
        assert chain.ordering_service.wait_for_active(timeout=5)
        blocks = chain.ordering_service.storage_handler.get_blocks_from_db(0)

        assert [block.index for block in blocks] == [0, 1]
        assert blocks[0].to_event_list()[0]["event"] == "genesis"
        assert blocks[1].to_event_list()[0]["event_id"] == "replay-after-genesis"
        assert blocks[1].previous_hash == blocks[0].hash
        assert sum(
            event.get("event_id") == "replay-after-genesis"
            for block in blocks
            for event in block.to_event_list()
        ) == 1
        assert len(chain.entity_event_index["recovery-test"]) == 1
        assert chain.ordering_service.commit_queue.empty()
        assert chain.ordering_service.blocks_created == 2
        assert chain.ordering_service.status is OrderingStatus.ACTIVE

        monkeypatch.setattr(
            ProofOfAuthority, "finalize_block", lambda _self, block, _name, **_kwargs: block
        )
        monkeypatch.setattr(
            ProofOfAuthority, "validate_block", lambda *_args: False
        )
        rejected_block = Block(
            index=2,
            events=[
                {
                    "event_id": "rejected-event",
                    "entity_id": "recovery-test",
                    "event": "rejected_event",
                    "timestamp": time.time(),
                }
            ],
            previous_hash=blocks[-1].hash,
        )

        with pytest.raises(ValueError, match="Consensus rejected ordered block"):
            chain.ordering_service.processor.block_manager.commit_block(rejected_block)
        persisted_blocks = chain.ordering_service.storage_handler.get_blocks_from_db(0)
        assert [block.index for block in persisted_blocks] == [0, 1]
        assert all(
            event.get("event_id") != "rejected-event"
            for block in persisted_blocks
            for event in block.to_event_list()
        )
        assert chain.ordering_service.status is OrderingStatus.MAINTENANCE
        assert chain.ordering_service.commit_queue.empty()
    finally:
        chain.shutdown()


@pytest.mark.parametrize("commit_before_snapshot", [False, True])
def test_sync_does_not_rewind_orderer_after_a_concurrent_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commit_before_snapshot: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sub_chain_base.settings, "BLOCK_INTERVAL", 0.02)
    monkeypatch.setattr(sub_chain_base, "_consumer_loop", lambda _chain: None)
    chain = SubChain("sync_commit_race", config={"db_url": f"sqlite:///{tmp_path / 'chain.db'}"})
    service = chain.ordering_service
    storage = service.storage_handler
    load_blocks = storage.get_blocks_from_db
    try:
        assert service.wait_for_active(timeout=5)
        if commit_before_snapshot:
            service.processor.block_manager.commit_block(Block(index=0, events=[], previous_hash=""))
        expected_index = 2 + int(commit_before_snapshot)

        def load_then_commit(start_index: int) -> list[Block]:
            snapshot = load_blocks(start_index)
            service.processor.block_manager.commit_block(
                Block(index=0, events=[], previous_hash="")
            )
            return snapshot

        monkeypatch.setattr(storage, "get_blocks_from_db", load_then_commit)
        chain.sync_chain()
        assert service.blocks_created == expected_index
        assert service.block_history[-1].index == expected_index - 1
        assert service.storage_handler.last_block.index == expected_index - 1

        service.processor.block_manager.commit_block(Block(index=0, events=[], previous_hash=""))
        blocks = load_blocks(0)
        assert [block.index for block in blocks] == list(range(expected_index + 1))
        assert blocks[-1].previous_hash == blocks[-2].hash
    finally:
        chain.shutdown()


def test_broken_chain_is_rejected_before_journal_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sub_chain_base, "_consumer_loop", lambda _chain: None)
    config = {"db_url": f"sqlite:///{tmp_path / 'chain.db'}"}
    chain = SubChain("broken_link", config=config)
    try:
        service = chain.ordering_service
        assert service.wait_for_active(timeout=5)
        block = Block(index=1, events=[], previous_hash="broken")
        sign_block(block, service.node_identity.node_id, service.node_identity.signing_keypair)
        service.storage_handler.save_block(block, chain.name)
    finally:
        chain.shutdown()

    def reject_replay(_service: OrderingService) -> None:
        pytest.fail("Journal replay must not start on a broken chain")

    monkeypatch.setattr(OrderingService, "_start_processing_thread", reject_replay)
    with pytest.raises(ValueError, match="Chain link BROKEN at block=1"):
        SubChain("broken_link", config=config)
