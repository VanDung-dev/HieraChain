from __future__ import annotations

import hashlib
from typing import Any

from hierachain.serialization import dumps_canonical_json

BLOCK_CONTRACT_VERSION = 1


def block_header(
    *,
    index: int,
    timestamp: float,
    previous_hash: str,
    nonce: int,
    merkle_root: str,
    creator_id: str | None,
) -> dict[str, Any]:
    return {
        "index": index,
        "timestamp": timestamp,
        "previous_hash": previous_hash,
        "nonce": nonce,
        "merkle_root": merkle_root,
        "creator_id": creator_id,
    }


def canonical_block_header(
    *,
    index: int,
    timestamp: float,
    previous_hash: str,
    nonce: int,
    merkle_root: str,
    creator_id: str | None,
) -> bytes:
    return dumps_canonical_json(
        block_header(
            index=index,
            timestamp=timestamp,
            previous_hash=previous_hash,
            nonce=nonce,
            merkle_root=merkle_root,
            creator_id=creator_id,
        )
    )


def calculate_block_hash(
    *,
    index: int,
    timestamp: float,
    previous_hash: str,
    nonce: int,
    merkle_root: str,
    creator_id: str | None,
) -> str:
    return hashlib.sha256(
        canonical_block_header(
            index=index,
            timestamp=timestamp,
            previous_hash=previous_hash,
            nonce=nonce,
            merkle_root=merkle_root,
            creator_id=creator_id,
        )
    ).hexdigest()
