"""Signed block persistence must serialize exactly the verified event snapshot."""

import os
import time
from pathlib import Path

import pytest

from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.core.block import Block, calculate_merkle_from_list
from hierachain.security.identity_loader import require_block_identity
from hierachain.security.verify.block_verifier import sign_block


@pytest.mark.parametrize("precomputed", [False, True])
@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_input_and_export_mutations_cannot_corrupt_signed_persistence(
    tmp_path: Path, backend: str, precomputed: bool,
) -> None:
    url = f"sqlite:///{tmp_path / 'blocks.db'}"
    if backend == "postgres":
        url = os.getenv("HRC_TEST_POSTGRES_URL", "")
        if not url:
            pytest.skip("HRC_TEST_POSTGRES_URL is required")
    identity, trusted = require_block_identity(None, None)
    name = f"ownership-{backend}-{precomputed}"
    store = OrderingStorageHandler({"db_url": url, "chain_name": name, "trusted_public_keys": trusted})
    events = [{"entity_id": "item", "event": "created", "timestamp": time.time(),
               "details": {"nested": {"value": "original"}}}]
    block = Block(0, events, previous_hash="0",
                  merkle_root=calculate_merkle_from_list(events) if precomputed else None)
    sign_block(block, identity.node_id, identity.signing_keypair)
    events[0]["details"]["nested"]["value"] = "changed-input"
    exported = block.to_event_list()
    exported[0]["details"]["nested"]["value"] = "changed-export"
    block.to_dict()["events"].clear()
    try:
        assert block.to_event_list()[0]["details"]["nested"]["value"] == "original"
        store.save_block(block, name)
        restored = store.get_blocks_from_db(0)
        assert len(restored) == 1
        assert restored[0].hash == block.hash
        assert restored[0].to_event_list() == block.to_event_list()
    finally:
        store.close()
