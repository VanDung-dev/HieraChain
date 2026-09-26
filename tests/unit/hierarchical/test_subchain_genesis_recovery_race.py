"""Regression coverage for SubChain journal replay and queue rehydration."""

import time
from pathlib import Path

import pytest

from hierachain.consensus.ordering.certifier import EventCertifier
from hierachain.consensus.ordering.types import OrderingStatus, PendingEvent
from hierachain.consensus.proof_of_authority import ProofOfAuthority
from hierachain.core.block import Block
from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.hierarchical.sub_chain import base as sub_chain_base
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.hierarchical.sub_chain.block import _process_and_finalize_single_block


def test_journal_replay_rehydrates_once_and_rejects_before_persisting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
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
            ProofOfAuthority, "finalize_block", lambda _self, block, _name: block
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

        assert not _process_and_finalize_single_block(chain, rejected_block)
        persisted_blocks = chain.ordering_service.storage_handler.get_blocks_from_db(0)
        assert [block.index for block in persisted_blocks] == [0, 1]
        assert all(
            event.get("event_id") != "rejected-event"
            for block in persisted_blocks
            for event in block.to_event_list()
        )
        assert chain.ordering_service.status is OrderingStatus.ACTIVE
    finally:
        chain.shutdown()
