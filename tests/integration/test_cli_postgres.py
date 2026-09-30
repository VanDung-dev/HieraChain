"""Live PostgreSQL verification of persisted block and event signatures."""

import os
from pathlib import Path

import orjson
import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hierachain.adapters.database.postgres_adapter import PostgresAdapter
from hierachain.cli.verify import verify_group
from hierachain.config.settings import settings
from hierachain.core.block import Block
from hierachain.security.verify.block_verifier import BlockVerifier
from hierachain.security.verify.signature_verifier import SignatureVerifier


@pytest.mark.integration
def test_postgres_cli_verifies_persisted_event_signatures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.getenv("HRC_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("HRC_TEST_POSTGRES_URL is not set")

    signer = Ed25519PrivateKey.generate()
    trust_file = tmp_path / "trusted.json"
    trust_file.write_bytes(orjson.dumps({"validator-1": signer.public_key().public_bytes_raw().hex()}))
    monkeypatch.setattr(settings, "BLOCK_TRUSTED_KEYS_FILE", str(trust_file))
    event = {
        "entity_id": "entity-1",
        "event": "created",
        "timestamp": 1.0,
        "details": {"sender_public_key": signer.public_key().public_bytes_raw().hex()},
    }
    event["signature"] = signer.sign(SignatureVerifier._get_signable_event_content(event)).hex()
    block = Block(index=0, events=[event], previous_hash="0", creator_id="validator-1")
    block.signature = signer.sign(BlockVerifier._get_signable_content(block)).hex()
    data = block.to_dict()
    data["chain_name"] = "p2-cli-test"
    data["metadata"] = {
        "creator_id": block.creator_id,
        "signature": block.signature,
        "merkle_root": block.merkle_root,
    }
    backend = PostgresAdapter(database_url=url)
    try:
        assert backend.save_block(data)
    finally:
        backend.close()

    runner = CliRunner()
    chain = runner.invoke(verify_group, ["chain", "--db", url])
    assert chain.exit_code == 0, chain.output
    audit = runner.invoke(verify_group, ["signatures", "--db", url])
    assert audit.exit_code == 0, audit.output
    assert "Events: 1 Valid, 0 Invalid" in audit.output

    event["signature"] = "00" * 64
    bad_block = Block(index=0, events=[event], previous_hash="0", creator_id="validator-1")
    bad_block.signature = signer.sign(BlockVerifier._get_signable_content(bad_block)).hex()
    data = bad_block.to_dict()
    data["chain_name"] = "p2-cli-test"
    data["metadata"] = {
        "creator_id": bad_block.creator_id,
        "signature": bad_block.signature,
        "merkle_root": bad_block.merkle_root,
    }
    backend = PostgresAdapter(database_url=url)
    try:
        assert backend.save_block(data)
    finally:
        backend.close()
    audit = runner.invoke(verify_group, ["signatures", "--db", url])
    assert audit.exit_code != 0
    assert "Events: 0 Valid, 1 Invalid" in audit.output
