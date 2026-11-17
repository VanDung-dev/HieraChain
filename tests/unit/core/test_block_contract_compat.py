from __future__ import annotations

from typing import Any

import pytest

from hierachain.adapters.database import SQLiteAdapter
from hierachain.core.block import Block
from hierachain.core.block_contract import (
    BLOCK_CONTRACT_VERSION,
    calculate_block_hash,
    canonical_block_header,
)
from hierachain.serialization import dumps_canonical_json

EVENTS: list[dict[str, Any]] = [
    {
        "entity_id": "asset-1",
        "event": "created",
        "timestamp": 1700000000.0,
        "details": {"site": "hanoi", "value": 1},
    },
    {
        "entity_id": "asset-1",
        "event": "approved",
        "timestamp": 1700000001.0,
        "details": {"reviewer": "alice"},
    },
]


def _fixed_block() -> Block:
    return Block(
        index=7,
        events=EVENTS,
        timestamp=1700000002.0,
        previous_hash="a" * 64,
        nonce=3,
        creator_id="node-1",
    )


def test_block_header_digest_matches_frozen_compatibility_vector() -> None:
    block = _fixed_block()

    assert block.merkle_root == "33e166c681cd81d08fef929b8cfab3253abb6f8ac769478527689db08099829b"
    assert block.hash == "e50d1449f63a92047a0c684d8763f7eac7951c0bbe413c4b30a507760fec98a5"


def test_block_header_canonical_bytes_match_frozen_compatibility_vector() -> None:
    block = _fixed_block()
    expected = (
        b'{"creator_id":"node-1","index":7,'
        b'"merkle_root":"33e166c681cd81d08fef929b8cfab3253abb6f8ac769478527689db08099829b",'
        b'"nonce":3,"previous_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
        b'"timestamp":1700000002.0}'
    )
    header = {
        "index": block.index,
        "timestamp": block.timestamp,
        "previous_hash": block.previous_hash,
        "nonce": block.nonce,
        "merkle_root": block.merkle_root,
        "creator_id": block.creator_id,
    }

    assert BLOCK_CONTRACT_VERSION == 1
    assert dumps_canonical_json(header) == expected
    assert canonical_block_header(**header) == expected
    assert calculate_block_hash(**header) == block.hash


def test_block_dict_round_trip_preserves_events_and_digest() -> None:
    block = _fixed_block()

    restored = Block.from_dict(block.to_dict())

    assert restored.to_dict() == block.to_dict()
    assert restored.hash == block.hash
    assert restored.merkle_root == block.merkle_root


def test_block_dict_round_trip_rejects_tampered_hash() -> None:
    payload = _fixed_block().to_dict()
    payload["hash"] = "0" * 64

    with pytest.raises(ValueError, match="Block hash MISMATCH"):
        Block.from_dict(payload)


def test_block_event_order_is_part_of_the_digest_contract() -> None:
    forward = Block(index=1, events=EVENTS, timestamp=1700000002.0)
    reversed_block = Block(index=1, events=list(reversed(EVENTS)), timestamp=1700000002.0)

    assert forward.merkle_root != reversed_block.merkle_root


def test_block_survives_sqlite_persistence_round_trip(tmp_path) -> None:
    block = _fixed_block()
    adapter = SQLiteAdapter(str(tmp_path / "block-contract.db"))
    try:
        assert adapter.save_block({
            "chain_name": "contract-chain",
            "index": block.index,
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "timestamp": block.timestamp,
            "nonce": block.nonce,
            "events": block.to_event_list(),
            "metadata": {
                "merkle_root": block.merkle_root,
                "creator_id": block.creator_id,
                "signature": block.signature,
            },
        })
        loaded = adapter.get_block_by_index(block.index, "contract-chain")
    finally:
        adapter.close()

    assert loaded is not None
    restored = Block.from_dict(loaded)
    assert restored.to_dict() == block.to_dict()
