"""Regression coverage for bounded pending state and 2PC retention."""

import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hierachain.config.settings import settings
from hierachain.hierarchical.sub_chain import SubChain
from hierachain.hierarchical.sub_chain.block import _process_and_finalize_single_block
from hierachain.hierarchical.transaction_manager import CrossChainTransactionManager
from hierachain.hierarchical.types import CrossChainTransaction


def test_subchain_pending_events_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SubChain, "_PENDING_EVENTS_LIMIT", 3)
    chain = object.__new__(SubChain)
    chain.name = "bounded"
    chain.lock = threading.Lock()
    chain.pending_events = []
    chain.ordering_service = SimpleNamespace(
        receive_event=Mock(side_effect=lambda **kwargs: f"id-{kwargs['event_data']['entity_id']}")
    )

    for index in range(6):
        chain.add_event({"entity_id": f"entity-{index}", "event": "created"})

    assert [event["entity_id"] for event in chain.pending_events] == [
        "entity-3", "entity-4", "entity-5"
    ]


def test_committed_blocks_remove_their_pending_events() -> None:
    block = SimpleNamespace(
        to_event_list=lambda: [{"event_id": "id-1"}, {"event_id": "id-2"}],
    )
    sub_chain = SimpleNamespace(
        block_processing_lock=threading.RLock(),
        lock=threading.RLock(),
        pending_events=[{"event_id": "id-1"}, {"event_id": "id-2"}, {"event_id": "id-3"}],
        add_block=Mock(return_value=True),
        world_state=SimpleNamespace(apply_block=Mock()),
        auto_submit_proof_if_needed=Mock(),
    )

    assert _process_and_finalize_single_block(sub_chain, block)
    assert sub_chain.pending_events == [{"event_id": "id-3"}]


def test_resolved_transactions_expire_but_unresolved_do_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "CROSS_CHAIN_TRANSACTION_TTL_SECONDS", 10)
    manager = object.__new__(CrossChainTransactionManager)
    manager.transactions = {}
    manager._phases = {}
    manager._durable_records = {}
    manager._activity_lock = threading.Lock()
    manager._active_owners = {}
    manager._journal_lock = threading.RLock()

    now = time.time()
    for tx_id, phase, updated_at in (
        ("resolved", "committed", now - 100),
        ("recent", "committed", now - 1),
        ("unresolved", "begin", now - 100),
    ):
        manager.transactions[tx_id] = CrossChainTransaction(
            transaction_id=tx_id,
            source_chain="source",
            destination_chain="destination",
            payload={},
            updated_at=updated_at,
        )
        manager._phases[tx_id] = phase
        manager._durable_records[tx_id] = {"phase": phase}

    manager._prune_resolved(now=now)

    assert set(manager.transactions) == {"recent", "unresolved"}
    assert set(manager._phases) == {"recent", "unresolved"}
    assert set(manager._durable_records) == {"recent", "unresolved"}
