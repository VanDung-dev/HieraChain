"""Regression coverage for mandatory trusted signatures on every block."""

import asyncio
import json
import sqlite3
import time

import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI

from hierachain.api.server import lifespan
from hierachain.cli.verify import verify_group
from hierachain.config.settings import settings
from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
from hierachain.hierarchical.channel.ledger import ChannelLedger
from hierachain.hierarchical.main_chain.base import MainChain
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.hierarchical.sub_chain.block import _process_and_finalize_single_block
from hierachain.security.identity_loader import (
    NodeIdentity,
    load_trusted_block_keys,
)
from hierachain.security.security_utils import KeyPair


def _identity_and_keys() -> tuple[NodeIdentity, dict[str, bytes]]:
    keypair = KeyPair.generate()
    identity = NodeIdentity({
        "node_id": "node-a",
        "msp_id": "OrgA-MSP",
        "signing_key": keypair.private_key,
        "signing_public_key": keypair.public_key,
        "transport_secret_key": "",
        "transport_public_key": "",
    })
    public_key = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(keypair.public_key)
    ).public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return identity, {identity.node_id: public_key}


def test_chain_requires_fixed_signer_and_trusted_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "VALIDATOR_IDENTITY_PATH", str(tmp_path / "missing.json"))
    with pytest.raises(RuntimeError, match="fixed node identity"):
        Blockchain()

    identity, keys = _identity_and_keys()
    with pytest.raises(RuntimeError, match="matching trusted block key"):
        Blockchain(node_identity=identity, trusted_public_keys={})

    chain = Blockchain(node_identity=identity, trusted_public_keys=keys)
    assert chain.chain[0].signature
    assert chain.is_chain_valid()

    block = chain.create_block([{"entity_id": "E1", "event": "updated"}])
    assert chain.add_block(block)
    assert chain.is_chain_valid()

    block.signature = None
    assert not chain.is_chain_valid()


def test_api_startup_rejects_missing_trust_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "BLOCK_TRUSTED_KEYS_FILE", str(tmp_path / "missing.json"))

    async def start_api() -> None:
        async with lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="Cannot load trusted block keys"):
        asyncio.run(start_api())


def test_trust_file_and_storage_preserve_signed_blocks(tmp_path) -> None:
    identity, keys = _identity_and_keys()
    trust_file = tmp_path / "trusted.json"
    trust_file.write_text(json.dumps({identity.node_id: identity.signing_public_key}))
    assert load_trusted_block_keys(str(trust_file)) == keys

    chain = Blockchain(node_identity=identity, trusted_public_keys=keys)
    handler = OrderingStorageHandler({
        "db_url": f"sqlite:///{tmp_path / 'blocks.db'}",
        "chain_name": chain.name,
        "trusted_public_keys": keys,
    })
    try:
        handler.save_block(chain.chain[0], chain.name)
        restored = handler.get_latest_block_from_db()
        assert restored is not None
        assert restored.creator_id == identity.node_id
        assert restored.signature == chain.chain[0].signature

        restored.signature = None
        with pytest.raises(ValueError, match="unsigned or untrusted"):
            handler.save_block(restored, chain.name)
    finally:
        handler.close()


def test_main_and_channel_blocks_are_signed() -> None:
    identity, keys = _identity_and_keys()
    main = MainChain(
        name="SignedMain",
        consensus_type="proof_of_authority",
        node_identity=identity,
        trusted_public_keys=keys,
    )
    main.consensus.config["block_interval"] = 0.0
    main.add_event({"entity_id": "E1", "event": "updated", "timestamp": time.time()})
    assert main.finalize_block() is not None
    assert main.is_chain_valid()

    ledger = ChannelLedger(node_identity=identity, trusted_public_keys=keys)
    assert ledger.add_event({"entity_id": "E1", "event": "updated"})
    block = ledger.finalize_block()
    assert block is not None and block.signature


def test_sub_chain_reloads_signed_genesis(monkeypatch, tmp_path) -> None:
    identity, keys = _identity_and_keys()
    monkeypatch.chdir(tmp_path)
    sub_chain = SubChain(
        name="SignedSub",
        domain_type="test",
        node_identity=identity,
        config={
            "db_url": f"sqlite:///{tmp_path / 'sub.db'}",
            "trusted_public_keys": keys,
        },
    )
    try:
        restored = sub_chain.ordering_service.storage_handler.get_latest_block_from_db()
        assert restored is not None and restored.signature
        assert sub_chain.is_chain_valid()

        sub_chain.running = False
        sub_chain.consumer_thread.join(timeout=2.0)
        sub_chain.consensus.config["block_interval"] = 0.0
        candidate = Block(
            index=0,
            events=[{"entity_id": "E1", "event": "updated", "timestamp": time.time()}],
            previous_hash="",
        )
        sub_chain.ordering_service.processor.block_manager.commit_block(candidate)
        committed = sub_chain.ordering_service.get_next_block()
        assert committed is not None
        assert _process_and_finalize_single_block(sub_chain, committed)
        assert sub_chain.is_chain_valid()
    finally:
        sub_chain.shutdown()

    reopened = SubChain(
        name="SignedSub",
        domain_type="test",
        node_identity=identity,
        config={
            "db_url": f"sqlite:///{tmp_path / 'sub.db'}",
            "trusted_public_keys": keys,
        },
    )
    try:
        assert len(reopened.chain) == 2
        assert reopened.is_chain_valid()
    finally:
        reopened.shutdown()


@pytest.mark.parametrize("command", ["chain", "signatures"])
def test_cli_rejects_unsigned_stored_block(tmp_path, command: str) -> None:
    db_path = tmp_path / "blocks.db"
    for chain_name in ("CliSignedChain", "OtherChain"):
        chain = Blockchain(name=chain_name)
        handler = OrderingStorageHandler({
            "db_url": f"sqlite:///{db_path}",
            "chain_name": chain.name,
            "trusted_public_keys": chain.trusted_public_keys,
        })
        try:
            handler.save_block(chain.chain[0], chain.name)
        finally:
            handler.close()

    valid_result = CliRunner().invoke(
        verify_group, [command, "--db", f"sqlite:///{db_path}"]
    )
    assert valid_result.exit_code == 0

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT metadata_json FROM blocks WHERE chain_name = 'OtherChain'"
        ).fetchone()
        assert row is not None
        metadata = json.loads(row[0])
        metadata.pop("signature")
        connection.execute(
            "UPDATE blocks SET metadata_json = ? WHERE chain_name = 'OtherChain'",
            (json.dumps(metadata),),
        )

    result = CliRunner().invoke(
        verify_group, [command, "--db", f"sqlite:///{db_path}"]
    )
    assert result.exit_code != 0
