"""Regression tests for block signature verification."""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from hierachain.core.block import Block
from hierachain.security.verify.block_verifier import (
    BlockVerifier,
    VerificationStatus,
    get_block_verifier,
)


def _pem_public_key(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _signed_block(
    private_key: Ed25519PrivateKey,
    previous_hash: str = "genesis-hash",
) -> Block:
    block = Block(
        index=1,
        events=[{"entity_id": "entity-1", "event": "updated"}],
        previous_hash=previous_hash,
        creator_id="validator-1",
    )
    message = BlockVerifier._get_signable_content(block)
    block.signature = private_key.sign(message).hex()
    return block


def _signed_genesis(private_key: Ed25519PrivateKey) -> Block:
    block = Block(
        index=0,
        events=[{"entity_id": "SYSTEM", "event": "genesis"}],
        previous_hash="0",
        creator_id="validator-1",
    )
    block.signature = private_key.sign(BlockVerifier._get_signable_content(block)).hex()
    return block


def test_verify_block_accepts_signature_with_explicit_trusted_key() -> None:
    private_key = Ed25519PrivateKey.generate()
    block = _signed_block(private_key)

    result = BlockVerifier().verify_block(
        block,
        public_key=_pem_public_key(private_key),
    )

    assert result.status is VerificationStatus.VALID


@pytest.mark.parametrize("key_mode", ["missing", "wrong"])
def test_verify_block_rejects_signature_without_matching_key(
    key_mode: str,
) -> None:
    signing_key = Ed25519PrivateKey.generate()
    block = _signed_block(signing_key)
    public_key = (
        None
        if key_mode == "missing"
        else _pem_public_key(Ed25519PrivateKey.generate())
    )

    result = BlockVerifier().verify_block(block, public_key=public_key)

    assert result.status is VerificationStatus.INVALID
    assert result.details is not None
    assert result.details["signature"] == "Block signature invalid"


def test_verify_block_rejects_well_formed_fake_signature_with_key() -> None:
    public_key = _pem_public_key(Ed25519PrivateKey.generate())
    block = Block(
        index=1,
        events=[{"entity_id": "entity-1", "event": "updated"}],
        previous_hash="genesis-hash",
        creator_id="validator-1",
        signature="ab" * 64,
    )

    result = BlockVerifier().verify_block(block, public_key=public_key)

    assert result.status is VerificationStatus.INVALID
    assert result.details is not None
    assert result.details["signature"] == "Block signature invalid"


def test_verify_block_rejects_empty_signature() -> None:
    block = Block(index=1, events=[], signature="")

    result = BlockVerifier().verify_block(block)

    assert result.status is VerificationStatus.INVALID
    assert result.details is not None
    assert result.details["signature"] == "Block signature malformed"


def test_verify_block_rejects_unsigned_block() -> None:
    block = Block(
        index=1,
        events=[{"entity_id": "entity-1", "event": "updated"}],
        previous_hash="genesis-hash",
    )

    result = BlockVerifier().verify_block(block)

    assert result.status is VerificationStatus.INVALID


def test_verify_block_rejects_unsigned_block_with_explicit_strict_mode() -> None:
    block = Block(index=1, events=[], previous_hash="genesis-hash")

    result = BlockVerifier(strict_mode=True).verify_block(block)

    assert result.status is VerificationStatus.INVALID
    assert result.details is not None
    assert result.details["signature"] == "Block signature missing"


def test_verify_block_rejects_stripped_signature_when_key_is_supplied() -> None:
    private_key = Ed25519PrivateKey.generate()
    block = _signed_block(private_key)
    block.signature = None

    result = BlockVerifier().verify_block(
        block, public_key=_pem_public_key(private_key)
    )

    assert result.status is VerificationStatus.INVALID
    assert result.details is not None
    assert result.details["signature"] == "Block signature missing for trusted creator"


def test_compatibility_mode_cannot_be_enabled() -> None:
    assert get_block_verifier(strict_mode=True).strict_mode is True
    with pytest.raises(ValueError, match="Unsigned block verification is not supported"):
        get_block_verifier(strict_mode=False)
    with pytest.raises(ValueError, match="Unsigned block verification is not supported"):
        BlockVerifier(strict_mode=False)


def test_verify_chain_uses_creator_key_from_trusted_key_map() -> None:
    private_key = Ed25519PrivateKey.generate()
    genesis = _signed_genesis(private_key)
    signed_block = _signed_block(private_key, previous_hash=genesis.hash)

    result = BlockVerifier().verify_chain(
        [genesis, signed_block],
        trusted_public_keys={"validator-1": _pem_public_key(private_key)},
    )

    assert result.status is VerificationStatus.VALID


def test_verify_chain_rejects_signed_block_without_trusted_key_map() -> None:
    private_key = Ed25519PrivateKey.generate()
    genesis = _signed_genesis(private_key)
    signed_block = _signed_block(private_key, previous_hash=genesis.hash)

    result = BlockVerifier().verify_chain([genesis, signed_block])

    assert result.status is VerificationStatus.INVALID
