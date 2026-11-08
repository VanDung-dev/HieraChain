"""Regression coverage for the P2 security findings SEC-01 through SEC-06."""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hierachain.core.block import Block
from hierachain.security.brute_force_protector import BruteForceProtector
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.block_verifier import BlockVerifier, VerificationStatus


def _pem_public_key(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _signed_chain(private_key: Ed25519PrivateKey) -> list[Block]:
    genesis = Block(
        index=0,
        events=[{"entity_id": "SYSTEM", "event": "genesis"}],
        previous_hash="0",
        creator_id="validator-1",
    )
    genesis.signature = private_key.sign(BlockVerifier._get_signable_content(genesis)).hex()
    child = Block(
        index=1,
        events=[{"entity_id": "entity-1", "event": "updated"}],
        previous_hash=genesis.hash,
        creator_id="validator-1",
    )
    child.signature = private_key.sign(BlockVerifier._get_signable_content(child)).hex()
    return [genesis, child]


def test_verify_chain_rejects_signed_suffix_without_genesis() -> None:
    private_key = Ed25519PrivateKey.generate()
    chain = _signed_chain(private_key)

    result = BlockVerifier().verify_chain(
        chain[1:],
        trusted_public_keys={"validator-1": _pem_public_key(private_key)},
    )

    assert result.status is VerificationStatus.INVALID
    assert result.details is not None
    assert result.details["invalid_blocks"][0]["errors"] == "Chain does not begin with the genesis block"


def test_file_lockout_is_visible_to_an_existing_protector(tmp_path: Path) -> None:
    config = {
        "max_failures": 2,
        "lockout_duration": 60,
        "tracking_window": 300,
        "storage_backend": "file",
        "storage_path": str(tmp_path / "file-lockout"),
    }
    first = BruteForceProtector(config)
    second = BruteForceProtector(config)

    assert not first.record_failure("192.0.2.10")
    assert first.record_failure("192.0.2.10")

    assert second.is_locked_out("192.0.2.10")


def test_sqlite_failure_window_and_lockout_are_shared_across_instances(tmp_path: Path) -> None:
    config = {
        "max_failures": 3,
        "lockout_duration": 60,
        "tracking_window": 300,
        "storage_backend": "sqlite",
        "storage_path": str(tmp_path / "shared-auth-state.db"),
    }
    first = BruteForceProtector(config)
    second = BruteForceProtector(config)
    ip = "192.0.2.20"

    assert not first.record_failure(ip)
    assert not second.record_failure(ip)
    assert second.get_failure_count(ip) == 2
    assert first.record_failure(ip)

    assert first.is_locked_out(ip)
    assert second.is_locked_out(ip)


def test_sqlite_failure_threshold_remains_atomic_across_worker_instances(tmp_path: Path) -> None:
    config = {
        "max_failures": 5,
        "lockout_duration": 60,
        "tracking_window": 300,
        "storage_backend": "sqlite",
        "storage_path": str(tmp_path / "concurrent-auth-state.db"),
    }
    protectors = [BruteForceProtector(config) for _ in range(2)]
    ip = "192.0.2.30"

    def record_attempt(index: int) -> bool:
        return protectors[index % 2].record_failure(ip)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(record_attempt, range(20)))

    assert all(protector.is_locked_out(ip) for protector in protectors)


def test_sqlite_attempt_window_is_shared_across_processes(tmp_path: Path) -> None:
    config = {
        "max_failures": 3,
        "lockout_duration": 60,
        "tracking_window": 300,
        "storage_backend": "sqlite",
        "storage_path": str(tmp_path / "process-shared-auth-state.db"),
    }
    protector = BruteForceProtector(config)
    ip = "192.0.2.40"
    assert not protector.record_failure(ip)

    script = (
        "import json, sys; "
        "from hierachain.security.brute_force_protector import BruteForceProtector; "
        "protector = BruteForceProtector(json.loads(sys.argv[1])); "
        "ip = sys.argv[2]; "
        "assert not protector.record_failure(ip); "
        "assert protector.record_failure(ip)"
    )
    subprocess.run(
        [sys.executable, "-c", script, json.dumps(config), ip],
        check=True,
        timeout=15,
    )

    assert protector.is_locked_out(ip)


@pytest.mark.parametrize("permissions", ["small", {"all": True}, ["all", None]])
def test_key_manager_fails_closed_for_malformed_loaded_permission_shapes(permissions: object) -> None:
    key_manager = KeyManager()
    api_key = "loaded-key-with-invalid-permissions"
    key_manager.storage[api_key] = {"user_id": "user-1", "permissions": permissions}

    assert all(
        not key_manager.has_permission(api_key, resource)
        for resource in ("events", "chains", "admin")
    )
    assert key_manager.get_permissions(api_key) == []


def test_key_manager_rejects_malformed_permissions_when_creating_a_key() -> None:
    with pytest.raises(ValueError, match="permissions must be a list of strings"):
        KeyManager().create_key("user-1", "small")  # type: ignore[arg-type]
