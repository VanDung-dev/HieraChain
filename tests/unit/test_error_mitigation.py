"""Fail-closed validation and recoverable encryption contracts."""

import base64
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from hierachain.error_mitigation import (
    DataValidator,
    EncryptionValidator,
    SecurityError,
    ValidationLevel,
)
from hierachain.serialization import dumps_json


def _check_details(value: Any) -> tuple[bool, str]:
    if value.get("unavailable"):
        raise RuntimeError("validation service unavailable")
    return True, ""


@pytest.mark.parametrize("level", list(ValidationLevel))
@pytest.mark.parametrize("auto_fix", [False, True])
def test_custom_validator_exception_invalidates_event(
    level: ValidationLevel, auto_fix: bool,
) -> None:
    validator = DataValidator(level=level, auto_fix=auto_fix, custom_validators={"details": _check_details})
    event = {"entity_id": "E1", "event": "created", "timestamp": 1.0, "details": {"unavailable": True}}
    result, fixed_event = validator.validate_event(event, index=7)
    assert not result.is_valid
    assert fixed_event == event
    assert any("Event[7]" in error and "Custom validator failed" in error for error in result.errors)


def test_custom_validator_failure_invalidates_batch() -> None:
    validator = DataValidator(custom_validators={"details": _check_details})
    events = [
        {"entity_id": "E1", "event": "created", "timestamp": 1.0, "details": {}},
        {"entity_id": "E2", "event": "created", "timestamp": 2.0, "details": {"unavailable": True}},
    ]
    result, fixed_events = validator.validate_events_batch(events)
    assert not result.is_valid
    assert fixed_events == events
    assert "Event[1]" in result.errors[0]


@pytest.mark.parametrize("custom_result", [None, (True,), ("yes", ""), (True, None)])
def test_malformed_custom_validator_result_invalidates_event(custom_result: Any) -> None:
    def malformed_validator(_value: Any) -> Any:
        return custom_result

    validator = DataValidator(custom_validators={"details": malformed_validator})
    result, _ = validator.validate_event({
        "entity_id": "E1", "event": "created", "timestamp": 1.0, "details": {},
    })
    assert not result.is_valid
    assert "Custom validator failed" in result.errors[0]


def test_encrypt_rejects_missing_key_resolver() -> None:
    validator = EncryptionValidator({"algorithm": "AES-256-GCM", "key_id": "key-1"})
    assert validator.validate_config()
    with pytest.raises(SecurityError):
        validator.encrypt_data("recoverable data")


def test_encryption_round_trip_after_key_rotation() -> None:
    keys = {"key-1": AESGCM.generate_key(bit_length=256)}
    validator = EncryptionValidator({"algorithm": "AES-256-GCM", "key_id": "key-1"}, key_resolver=keys.__getitem__)
    payload = validator.encrypt_data("Dữ liệu nghiệp vụ")
    assert payload["key_id"] == "key-1"
    assert "key" not in payload
    assert len(payload["iv"]) == 12
    assert len(payload["tag"]) == 16
    assert validator.encrypt_data("Dữ liệu nghiệp vụ")["iv"] != payload["iv"]

    keys["key-2"] = AESGCM.generate_key(bit_length=256)
    reopened = EncryptionValidator({"algorithm": "AES-256-GCM", "key_id": "key-2"}, key_resolver=keys.__getitem__)
    assert reopened.decrypt_data(payload) == "Dữ liệu nghiệp vụ"
    assert reopened.encrypt_data("")["key_id"] == "key-2"
    assert reopened.decrypt_data(reopened.encrypt_data("")) == ""
    del keys["key-1"]
    with pytest.raises(SecurityError):
        reopened.decrypt_data(payload)


@pytest.mark.parametrize("field", ["ciphertext", "tag", "iv", "key_id", "algorithm", "timestamp"])
def test_encrypted_envelope_rejects_tampering(field: str) -> None:
    key = AESGCM.generate_key(bit_length=256)
    keys = {"key-1": key, "alias": key}
    validator = EncryptionValidator({"algorithm": "AES-256-GCM", "key_id": "key-1"}, key_resolver=keys.__getitem__)
    payload = validator.encrypt_data("business data")
    if field in ("ciphertext", "tag", "iv"):
        value = payload[field]
        payload[field] = bytes([value[0] ^ 1]) + value[1:]
    elif field == "key_id":
        payload[field] = "alias"
    elif field == "algorithm":
        payload[field] = "AES-128-GCM"
    else:
        payload[field] += 1
    with pytest.raises(SecurityError):
        validator.decrypt_data(payload)


@pytest.mark.parametrize("key_id, key", [(None, b"x" * 32), ("key-1", b"short"), ("key-1", "x" * 32)])
def test_encrypt_rejects_invalid_key_configuration(key_id: Any, key: Any) -> None:
    def resolve_key(_key_id: str) -> bytes:
        return key

    validator = EncryptionValidator({"algorithm": "AES-256-GCM", "key_id": key_id}, key_resolver=resolve_key)
    with pytest.raises(SecurityError):
        validator.encrypt_data("business data")


@pytest.mark.parametrize("field", ["key_id", "tag", "iv"])
def test_decrypt_rejects_incomplete_or_malformed_envelope(field: str) -> None:
    keys = {"key-1": AESGCM.generate_key(bit_length=256)}
    validator = EncryptionValidator({"algorithm": "AES-256-GCM", "key_id": "key-1"}, key_resolver=keys.__getitem__)
    payload = validator.encrypt_data("business data")
    if field == "key_id":
        del payload[field]
    elif field == "iv":
        payload[field] = b"short"
    else:
        payload[field] = "invalid"
    with pytest.raises(SecurityError):
        validator.decrypt_data(payload)


def test_decryption_recovers_retained_key_in_new_process(tmp_path: Path) -> None:
    key = AESGCM.generate_key(bit_length=256)
    key_file = tmp_path / "retained-key"
    key_file.write_bytes(key)
    key_file.chmod(0o600)
    validator = EncryptionValidator(
        {"algorithm": "AES-256-GCM", "key_id": "retained-key"},
        key_resolver={"retained-key": key}.__getitem__,
    )
    payload = validator.encrypt_data("Dữ liệu khôi phục")
    serializable = {
        field: base64.b64encode(value).decode("ascii") if isinstance(value, bytes) else value
        for field, value in payload.items()
    }
    script = """
import json
import base64
import sys
from pathlib import Path
from hierachain.error_mitigation import EncryptionValidator

def resolve_key(key_id: str) -> bytes:
    assert key_id == 'retained-key'
    return Path(sys.argv[1]).read_bytes()

payload = json.loads(sys.stdin.buffer.read())
for field in ('ciphertext', 'tag', 'iv'):
    payload[field] = base64.b64decode(payload[field])
reader = EncryptionValidator({'algorithm': 'AES-256-GCM'}, key_resolver=resolve_key)
assert reader.decrypt_data(payload) == 'Dữ liệu khôi phục'
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(key_file)], input=dumps_json(serializable).encode("utf-8"),
        capture_output=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr.decode()
