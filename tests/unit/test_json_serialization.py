"""JSON migration regressions for persisted digests and runtime responses."""

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.responses import JSONResponse

from hierachain.api.storage.ipfs_client import IPFSClient
from hierachain.consensus.bft.helpers import hash_request
from hierachain.consensus.ordering.storage import _block_from_dict
from hierachain.monitoring.alert_system import WebhookNotifier
from hierachain.monitoring.types import Alert, AlertCategory, AlertSeverity
from hierachain.serialization import dumps_canonical_json, dumps_json, loads_json


@pytest.mark.parametrize("details", [
    {"text": "Tiếng Việt 🌱", "nested": {"z": 0, "a": [True, None]}},
    {"measurements": [1e-5, 1e-7, 1e16, 1e20, -0.0, 1.2345678901234567]},
    {"large_integer": 2**80, "negative_integer": -(2**80)},
    {"keys": {2: {"z": "two", "a": 1}, 10: {"z": "ten", "a": 2}}},
    {"keys": {None: "empty"}},
    {"keys": {False: "no", True: "yes"}},
    {"keys": {0.00001: "small", 10.0: "large"}},
])
def test_bft_digest_preserves_legacy_json_bytes(details: dict[str, Any]) -> None:
    request = {"operation": {"entity_id": "asset-1", "details": details}}
    # This fixed encoder configuration is the established BFT request format.
    legacy = json.dumps(
        request, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")

    assert dumps_canonical_json(request) == legacy
    assert hash_request(request) == hashlib.sha256(legacy).hexdigest()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_cannot_become_null_in_request_digests(value: float) -> None:
    with pytest.raises(ValueError, match="JSON compliant"):
        hash_request({"operation": {"details": {"measurements": [value]}}})


def test_canonical_json_rejects_cycles_but_allows_shared_values() -> None:
    shared = {"text": "valid"}
    assert loads_json(dumps_canonical_json([shared, shared])) == [shared, shared]
    circular: list[Any] = []
    circular.append(circular)
    with pytest.raises(ValueError, match="Circular"):
        dumps_canonical_json(circular)


def test_json_response_uses_utf8_bytes_and_preserves_metadata() -> None:
    response = JSONResponse(
        {"message": "Tiếng Việt 🌱"}, status_code=403, headers={"X-Reason": "denied"},
    )
    assert response.body == b'{"message":"Ti\xe1\xba\xbfng Vi\xe1\xbb\x87t \xf0\x9f\x8c\xb1"}'
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/json"
    assert response.headers["x-reason"] == "denied"
    assert int(response.headers["content-length"]) == len(response.body)


@pytest.mark.parametrize("raw", [b"NaN", b"Infinity", b"-Infinity", b"1e400", b"-1e400"])
def test_json_reader_rejects_non_finite_numbers(raw: bytes) -> None:
    with pytest.raises(json.JSONDecodeError):
        loads_json(raw)


def test_repeated_json_round_trips_preserve_large_integers_and_unicode() -> None:
    original = {
        "name": "Thiết bị 🌱", "large": 2**80 + 1, "negative": -(2**80 + 1),
        "measurements": [1e-5, 1.2345678901234567, -0.0], "values": [True, False, None],
    }
    current = original
    for _ in range(100):
        current = loads_json(dumps_json(current).encode("utf-8"))
    assert current == original
    assert isinstance(current["large"], int)
    assert dumps_canonical_json(current) == dumps_canonical_json(original)


def test_json_writer_rejects_unknown_objects_without_coercion() -> None:
    with pytest.raises(TypeError):
        dumps_json({"value": object()})


def test_history_with_a_different_float_encoding_is_rejected() -> None:
    # Frozen bytes from the previous encoder; no optional codec is needed to
    # verify that old history is rejected rather than silently rehashed.
    legacy_bytes = (
        b'{"data":{"reading":0.00001},"entity_id":"asset-1",'
        b'"event":"updated","event_id":"legacy-value","timestamp":1.0}'
    )
    event = loads_json(legacy_bytes)
    assert event["data"]["reading"] == 1e-5
    assert dumps_canonical_json(event) != legacy_bytes
    historical = {
        "index": 1, "timestamp": 1.0, "previous_hash": "prev", "hash": "historical-hash",
        "merkle_root": hashlib.sha256(legacy_bytes).hexdigest(), "events": [event],
    }
    with pytest.raises(ValueError, match="Merkle root MISMATCH"):
        _block_from_dict(historical, {})


def test_package_does_not_import_optional_json_codecs() -> None:
    package = Path(__file__).resolve().parents[2] / "hierachain"
    optional_imports: list[str] = []
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import) and any(alias.name == "orjson" for alias in node.names):
                optional_imports.append(f"{path.relative_to(package)}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom) and node.module == "orjson":
                optional_imports.append(f"{path.relative_to(package)}:{node.lineno}")
    assert optional_imports == []


def test_ipfs_reads_json_from_http_response_bytes() -> None:
    cid = "test-cid"
    replies = {
        "/api/v0/add": {"Hash": cid},
        "/api/v0/pin/ls": {"Keys": {cid: {}}},
        "/api/v0/files/stat": {"Size": 1, "note": "Thiết bị"},
        "/api/v0/version": {"Version": "test-version"},
    }

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=dumps_json(replies[request.url.path]).encode("utf-8"))

    with IPFSClient(encryption_key=os.urandom(32)) as client:
        client._client = httpx.Client(base_url="http://ipfs.test", transport=httpx.MockTransport(respond))
        assert client.upload_bytes(b"payload", encrypt=False)["cid"] == cid
        assert client.list_pins() == [cid]
        assert client.get_stats(cid) == replies["/api/v0/files/stat"]
        assert client.get_daemon_version() == {"version": "test-version"}


def test_webhook_sends_utf8_json_and_retains_configured_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(record)) as http_client:
        monkeypatch.setattr("hierachain.monitoring.alert_system.httpx.post", http_client.post)
        notifier = WebhookNotifier({
            "url": "http://webhook.test/alerts", "enabled": True,
            "headers": {"X-Source": "test", "content-type": "application/vnd.hierachain+json"},
        })
        alert = Alert(
            alert_id="alert-1", timestamp=1.0, severity=AlertSeverity.WARNING,
            category=AlertCategory.SYSTEM, title="Cảnh báo", description="Thiết bị",
            source_component="test",
        )
        assert notifier.send_alert(alert)

    assert len(sent) == 1
    assert sent[0].headers["content-type"] == "application/vnd.hierachain+json"
    assert sent[0].headers["x-source"] == "test"
    assert "Cảnh báo".encode("utf-8") in sent[0].content
    assert loads_json(sent[0].content) == alert.to_dict()
