"""Integrity checks for blocks reconstructed from persistent storage."""

from __future__ import annotations

import threading
from copy import deepcopy
from types import SimpleNamespace

import pytest

from hierachain.consensus.ordering.storage import _block_from_dict
from hierachain.core.block import Block
from hierachain.hierarchical.sub_chain.ordering import _apply_rehydrated_blocks


def test_reconstructed_genesis_rejects_event_payload_tampering() -> None:
    block = Block(
        index=0,
        events=[
            {
                "entity_id": "entity-1",
                "event": "created",
                "timestamp": 1.0,
                "details": {"value": "original"},
            }
        ],
        previous_hash="0",
    )
    data = deepcopy(block.to_dict())
    data["events"][0]["details"]["value"] = "tampered"

    with pytest.raises(ValueError, match="Block Merkle root MISMATCH! block=0"):
        _block_from_dict(data, {})


def test_rehydration_does_not_accept_an_invalid_chain() -> None:
    sub_chain = SimpleNamespace(
        name="test-chain",
        lock=threading.RLock(),
        entity_event_index={},
        chain=[],
        total_events=0,
        event_type_counts={},
        world_state=SimpleNamespace(clear=lambda: None, apply_block=lambda _block: None),
        ordering_service=SimpleNamespace(block_history=[], blocks_created=0),
        is_chain_valid=lambda: False,
    )

    with pytest.raises(ValueError, match="failed integrity validation after rehydration"):
        _apply_rehydrated_blocks(sub_chain, [SimpleNamespace(index=0, events=[])])
