"""Regression coverage for the signed quarantine report contract."""

import hashlib
import hmac
import json
import math
import secrets
from dataclasses import fields
from typing import Any

import pytest

from hierachain.cluster.lockdown_types import QuarantineReport


def _signed_report() -> tuple[QuarantineReport, str]:
    secret_key = secrets.token_hex(32)
    report = QuarantineReport(
        node_id="node-α", timestamp=1700000000.125, pending_event_ids=["event-1", "event-2"],
        last_block_index=7, last_block_hash="a" * 64, total_pending=2,
    )
    report.signature = report.compute_signature(secret_key)
    return report, secret_key


def test_canonical_payload_and_json_round_trip() -> None:
    report, secret_key = _signed_report()
    expected_payload = (
        '{"last_block_hash":"' + "a" * 64 + '","last_block_index":7,'
        '"lockdown_type":"quarantine_report","msg_type":"cluster_lockdown",'
        '"node_id":"node-α","pending_event_ids":["event-1","event-2"],'
        '"timestamp":1700000000.125,"total_pending":2}'
    ).encode("utf-8")
    assert report.signature == hmac.new(secret_key.encode(), expected_payload, hashlib.sha256).hexdigest()[:32]
    assert {item.name for item in fields(report)} <= report.to_dict().keys()
    reordered = dict(reversed(list(report.to_dict().items())))
    restored = QuarantineReport.from_dict(json.loads(json.dumps(reordered)))
    assert restored.to_dict() == report.to_dict()
    assert restored.verify_signature(secret_key)
    original_signature = report.signature
    report.signature = "excluded-from-payload"
    assert report.compute_signature(secret_key) == original_signature


@pytest.mark.parametrize(("field_name", "changed_value"), [
    ("node_id", "node-other"),
    ("timestamp", math.nextafter(1700000000.125, math.inf)),
    ("last_block_index", 8), ("last_block_hash", "b" * 64), ("total_pending", 3),
    ("pending_event_ids", ["event-other", "event-2"]),
    ("pending_event_ids", ["event-1"]),
    ("pending_event_ids", ["event-1", "event-2", "event-3"]),
    ("pending_event_ids", ["event-2", "event-1"]),
])
def test_each_report_field_is_authenticated(field_name: str, changed_value: Any) -> None:
    report, secret_key = _signed_report()
    payload = report.to_dict()
    payload[field_name] = changed_value
    assert not QuarantineReport.from_dict(payload).verify_signature(secret_key)


def test_wrong_key_and_old_partial_signature_are_rejected() -> None:
    report, secret_key = _signed_report()
    assert not report.verify_signature(secrets.token_hex(32))
    old_payload = f"{report.node_id}:{report.timestamp}:{report.last_block_index}".encode()
    report.signature = hmac.new(secret_key.encode(), old_payload, hashlib.sha256).hexdigest()[:32]
    assert not report.verify_signature(secret_key)


@pytest.mark.parametrize(("field_name", "changed_value"), [
    ("msg_type", "other_message"), ("lockdown_type", "lockdown"),
])
def test_changed_message_type_is_rejected(field_name: str, changed_value: str) -> None:
    report, _ = _signed_report()
    payload = report.to_dict()
    payload[field_name] = changed_value
    with pytest.raises(ValueError, match="message type"):
        QuarantineReport.from_dict(payload)


@pytest.mark.parametrize("signature", ["", None, 123, b"invalid", "💥", "0" * 32])
def test_malformed_signature_returns_false(signature: Any) -> None:
    report, secret_key = _signed_report()
    report.signature = signature
    assert not report.verify_signature(secret_key)


@pytest.mark.parametrize("timestamp", [math.nan, math.inf, -math.inf])
def test_nonfinite_timestamp_cannot_be_signed_or_verified(timestamp: float) -> None:
    report, secret_key = _signed_report()
    report.timestamp = timestamp
    assert not report.verify_signature(secret_key)
    with pytest.raises(ValueError):
        report.compute_signature(secret_key)


def test_default_report_round_trip() -> None:
    secret_key = secrets.token_hex(32)
    report = QuarantineReport(node_id="node-1", timestamp=1700000000.0)
    report.signature = report.compute_signature(secret_key)
    assert QuarantineReport.from_dict(report.to_dict()).verify_signature(secret_key)
