"""CLI verification against persisted blocks and private key file permissions."""

import os
import stat
from pathlib import Path

import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.cli.key import key_group
from hierachain.cli.verify import verify_group
from hierachain.config.settings import settings
from hierachain.core.block import Block
from hierachain.security.verify.block_verifier import BlockVerifier
from hierachain.security.verify.signature_verifier import SignatureVerifier
from hierachain.serialization import dumps_json, loads_json


def test_key_file_is_private_and_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "validator.json"
    runner = CliRunner()
    created = runner.invoke(key_group, ["generate", "--output", str(path)])
    assert created.exit_code == 0, created.output
    data = loads_json(path.read_bytes())
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert data["private_key"] not in created.output
    assert runner.invoke(key_group, ["verify", "--input", str(path)]).exit_code == 0
    assert data["private_key"] not in runner.invoke(
        key_group, ["show", "--input", str(path)]
    ).output
    assert runner.invoke(key_group, ["generate", "--output", str(path)]).exit_code != 0
    assert loads_json(path.read_bytes()) == data


def test_verify_cli_rejects_empty_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    signer = Ed25519PrivateKey.generate()
    trust_file = tmp_path / "trusted.json"
    trust_file.write_bytes(dumps_json({"validator-1": signer.public_key().public_bytes_raw().hex()}).encode("utf-8"))
    monkeypatch.setattr(settings, "BLOCK_TRUSTED_KEYS_FILE", str(trust_file))
    db_path = tmp_path / "empty.db"
    backend = SQLiteAdapter(str(db_path))
    backend.close()
    for command in ("chain", "signatures"):
        result = CliRunner().invoke(verify_group, [command, "--db", str(db_path)])
        assert result.exit_code != 0
        assert "No named block chains" in result.output


def test_verify_cli_checks_persisted_event_signatures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    signer = Ed25519PrivateKey.generate()
    trust_file = tmp_path / "trusted.json"
    trust_file.write_bytes(dumps_json({"validator-1": signer.public_key().public_bytes_raw().hex()}).encode("utf-8"))
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
    block_data = block.to_dict()
    block_data["chain_name"] = "cli-test"
    block_data["metadata"] = {
        "creator_id": block.creator_id,
        "signature": block.signature,
        "merkle_root": block.merkle_root,
    }
    db_path = tmp_path / "blocks.db"
    backend = SQLiteAdapter(str(db_path))
    try:
        assert backend.save_block(block_data)
    finally:
        backend.close()

    runner = CliRunner()
    chain = runner.invoke(verify_group, ["chain", "--db", str(db_path)])
    assert chain.exit_code == 0, chain.output
    audit = runner.invoke(verify_group, ["signatures", "--db", str(db_path)])
    assert audit.exit_code == 0, audit.output
    assert "Events: 1 Valid, 0 Invalid" in audit.output
    assert "Unsigned events: 0" in audit.output

    event["signature"] = os.urandom(64).hex()
    bad_block = Block(index=0, events=[event], previous_hash="0", creator_id="validator-1")
    bad_block.signature = signer.sign(BlockVerifier._get_signable_content(bad_block)).hex()
    bad_data = bad_block.to_dict()
    bad_data["chain_name"] = "cli-test"
    bad_data["metadata"] = {
        "creator_id": bad_block.creator_id,
        "signature": bad_block.signature,
        "merkle_root": bad_block.merkle_root,
    }
    backend = SQLiteAdapter(str(db_path))
    try:
        assert backend.save_block(bad_data)
    finally:
        backend.close()
    audit = runner.invoke(verify_group, ["signatures", "--db", str(db_path)])
    assert audit.exit_code != 0
    assert "Events: 0 Valid, 1 Invalid" in audit.output
