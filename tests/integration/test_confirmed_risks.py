"""Real authenticated API, ordering, signed SQLite persistence and shutdown regressions."""

import copy
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.api.admin.endpoints import router as admin_router
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.api.ledger.events import router as events_router
from hierachain.api.storage.encryption import AESEncryption
from hierachain.config.settings import settings
from hierachain.consensus.ordering.certifier import EventCertifier
from hierachain.consensus.ordering.processor import OrderingProcessor
from hierachain.consensus.ordering.service import OrderingService
from hierachain.consensus.ordering.storage import OrderingStorageHandler
from hierachain.consensus.ordering.types import (
    EventStatus,
    OrderingBackpressureError,
    PendingEvent,
)
from hierachain.hierarchical.sub_chain.base import SubChain
from hierachain.security.identity_loader import NodeIdentity
from hierachain.security.key_manager import KeyManager
from hierachain.security.security_utils import KeyPair, verify_signature
from hierachain.security.verify.api_key_verifier import APIKeyVerifier
from hierachain.security.verify.block_verifier import get_block_verifier
from hierachain.security.verify.signature_verifier import SignatureVerifier


@pytest.fixture
def identity() -> tuple[NodeIdentity, dict[str, bytes]]:
    pair = KeyPair.generate()
    node = NodeIdentity(
        dict(
            node_id="confirmation",
            msp_id="Audit",
            signing_key=pair.private_key,
            signing_public_key=pair.public_key,
            transport_secret_key="",
            transport_public_key="",
        )
    )
    public = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(pair.public_key)
    ).public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return node, {"confirmation": public}


@dataclass
class Harness:
    chain: SubChain
    client: TestClient
    headers: dict
    insufficient: dict
    finished: threading.Event
    processed: list = field(default_factory=list)

    def persisted(self) -> list[dict[str, Any]]:
        config = self.chain.ordering_service.config.copy()
        self.chain.shutdown()
        assert not self.chain.ordering_service.processing_thread.is_alive()
        assert not self.chain.consumer_thread.is_alive()
        reader = OrderingStorageHandler(config)
        try:
            blocks = reader.get_blocks_from_db(0)
            assert all(
                get_block_verifier().verify_block_signature(
                    block, self.chain.trusted_public_keys[block.creator_id]
                )
                for block in blocks
            )
            return [
                row
                for block in blocks[1:]
                for row in block.to_event_list()
                if row.get("entity_id") != "system_consensus"
            ]
        finally:
            reader.close()


@pytest.fixture
def harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identity: tuple
) -> Iterator[Harness]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'main.db'}")
    monkeypatch.setattr(settings, "BLOCK_INTERVAL", 0.0)
    finished = threading.Event()
    processed = []
    original = OrderingProcessor._handle_processed_batch

    async def observe(self: OrderingProcessor, batch: list[PendingEvent]) -> None:
        processed.extend(batch)
        try:
            return await original(self, batch)
        finally:
            finished.set()

    monkeypatch.setattr(OrderingProcessor, "_handle_processed_batch", observe)
    node, trusted = identity
    chain = SubChain(
        "confirmation",
        node_identity=node,
        config={
            "storage_backend": "sqlite",
            "trusted_public_keys": trusted,
            "block_size": 1,
            "batch_size": 1,
            "batch_timeout": 0.1,
        },
    )
    keys = KeyManager()
    good = keys.create_key("review-authorized", ["events", "chains"])
    insufficient = keys.create_key("review-no-permissions", [])
    app = FastAPI()
    app.state.auth_verifier = APIKeyVerifier(
        {
            "enabled": True,
            "key_location": "header",
            "key_name": "X-API-Key",
            "cache_ttl": 0,
        },
        key_manager=keys,
    )
    app.include_router(events_router)
    app.include_router(admin_router)
    app.dependency_overrides[get_hierarchy_manager] = lambda: SimpleNamespace(
        get_sub_chain=lambda name: chain
    )
    # Only manager lookup is replaced. Auth, real SubChain, worker, consensus and storage run normally.
    with TestClient(app) as client:
        result = Harness(
            chain,
            client,
            {"X-API-Key": good},
            {"X-API-Key": insufficient},
            finished,
            processed,
        )
        try:
            yield result
        finally:
            result.chain.shutdown()
            keys.key_cache.clear()
            keys.permission_cache.clear()


@pytest.mark.parametrize("valid_signature", [False, True])
@pytest.mark.parametrize("prefix,payload", [("", "hello"), ("0x", "hello"), ("0x", "")])
def test_regular_api_checks_signature_before_persistence(
    harness: Harness, valid_signature: bool, prefix: str, payload: str
) -> None:
    pair = KeyPair.generate()
    signature = pair.sign(payload.encode()) if valid_signature else "00" * 64
    assert (
        verify_signature(pair.public_key, payload.encode(), signature)
        == valid_signature
    )
    signature = prefix + signature
    body = dict(
        entity_id="ordinary",
        event_type="created",
        details={"payload": payload},
        sender=prefix + pair.public_key,
        signature=signature,
    )
    response = harness.client.post(
        "/chains/confirmation/events", json=body, headers=harness.headers
    )
    assert response.status_code == 200, response.text
    assert harness.finished.wait(3), "ordering did not finish"
    assert harness.processed[0].status == (
        EventStatus.CERTIFIED if valid_signature else EventStatus.REJECTED
    )
    rows = harness.persisted()
    assert len(rows) == int(valid_signature)
    if valid_signature:
        assert rows[0]["signature"] == signature
        assert rows[0]["sender"] == body["sender"]
        assert rows[0]["submitted_by"] == body["sender"]


@pytest.mark.parametrize("valid_signature", [False, True])
def test_orderer_control_preserved_sender_checks_signature(
    harness: Harness, valid_signature: bool
) -> None:
    pair = KeyPair.generate()
    signature = pair.sign(b"hello") if valid_signature else "00" * 64
    event = dict(
        entity_id="direct-control",
        event="created",
        timestamp=time.time(),
        details={"payload": "hello"},
        sender=pair.public_key,
        signature=signature,
    )
    harness.chain.ordering_service.receive_event(event, "confirmation", "confirmation")
    assert harness.finished.wait(3)
    expected = EventStatus.CERTIFIED if valid_signature else EventStatus.REJECTED
    assert harness.processed[0].status == expected
    rows = harness.persisted()
    assert len(rows) == int(valid_signature)


def test_unsigned_regular_payload_remains_supported(harness: Harness) -> None:
    response = harness.client.post(
        "/chains/confirmation/events",
        headers=harness.headers,
        json={
            "entity_id": "unsigned",
            "event_type": "created",
            "details": {"payload": "hello"},
        },
    )
    assert response.status_code == 200, response.text
    assert harness.finished.wait(3)
    assert harness.processed[0].status is EventStatus.CERTIFIED
    rows = harness.persisted()
    assert len(rows) == 1
    assert rows[0]["details"] == {"payload": "hello"}


def secure_body(payload: bool = True, **fields: Any) -> dict[str, Any]:
    pair = KeyPair.generate()
    body = dict(
        entity_id="secure",
        event_type="created",
        details={"payload": "hello"} if payload else {"label": "hello"},
        sender="0x" + pair.public_key,
    )
    body.update(fields)
    body["signature"] = "0x" + pair.sign(SignatureVerifier.get_canonical_bytes(body))
    assert SignatureVerifier().verify_event_signature(body, body["sender"])
    return body


@pytest.mark.parametrize("with_payload", [True, False])
@pytest.mark.parametrize("timestamp_mode", ["omitted", "null", "current"])
def test_secure_acknowledgement_against_durable_outcome(
    harness: Harness, with_payload: bool, timestamp_mode: str
) -> None:
    fields = (
        {}
        if timestamp_mode == "omitted"
        else {
            "timestamp": None if timestamp_mode == "null" else time.time(),
            "chain_id": "confirmation",
            "nonce": "unique-request",
        }
    )
    body = secure_body(with_payload, **fields)
    response = harness.client.post(
        "/api/admin/chains/confirmation/secure-events",
        json=body,
        headers=harness.headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"
    assert harness.finished.wait(3)
    expected = EventStatus.CERTIFIED
    assert harness.processed[0].status == expected
    rows = harness.persisted()
    assert len(rows) == 1
    assert rows[0]["event"] == body["event_type"]


def test_tampered_secure_signature_is_rejected_at_http(harness: Harness) -> None:
    body = secure_body()
    body["details"]["payload"] = "tampered"
    response = harness.client.post(
        "/api/admin/chains/confirmation/secure-events",
        json=body,
        headers=harness.headers,
    )
    assert response.status_code == 422, response.text
    assert harness.chain.ordering_service.pending_events == {}
    assert harness.persisted() == []


def test_shutdown_waits_for_inflight_worker_before_closing_resources(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = harness.chain.ordering_service
    entered = threading.Event()
    release = threading.Event()
    original = service.processor._handle_batch_logic
    closed: list[tuple[str, bool]] = []

    async def delayed(*args: Any, **kwargs: Any) -> float:
        entered.set()
        assert release.wait(10)
        return await original(*args, **kwargs)

    def observe_close(name: str, resource: Any) -> None:
        close = resource.close

        def observed() -> None:
            closed.append((name, service.processing_thread.is_alive()))
            close()

        monkeypatch.setattr(resource, "close", observed)

    monkeypatch.setattr(service.processor, "_handle_batch_logic", delayed)
    observe_close("storage", service.storage_handler)
    observe_close("journal", service.journal)
    assert entered.wait(2)
    timer = threading.Timer(5.2, release.set)
    timer.start()
    try:
        service.shutdown()
        assert not service.processing_thread.is_alive()
        assert closed == [("storage", False), ("journal", False)]
    finally:
        release.set()
        timer.cancel()
        timer.join()


@pytest.mark.parametrize("secure", [False, True])
def test_auth_controls(harness: Harness, secure: bool) -> None:
    body = (
        secure_body()
        if secure
        else dict(entity_id="auth-control", event_type="created", details={})
    )
    route = (
        "/api/admin/chains/confirmation/secure-events"
        if secure
        else "/chains/confirmation/events"
    )
    missing = harness.client.post(route, json=body)
    invalid = harness.client.post(
        route, json=body, headers={"X-API-Key": "invalid-review-key"}
    )
    denied = harness.client.post(route, json=body, headers=harness.insufficient)
    assert missing.status_code == 401, missing.text
    assert invalid.status_code == 401, invalid.text
    assert denied.status_code == 403, denied.text
    assert harness.chain.ordering_service.pending_events == {}
    assert harness.persisted() == []


@pytest.mark.parametrize("nonce_mode", ["omitted", "null", "valid"])
def test_cid_nonce_http_and_persistence(harness: Harness, nonce_mode: str) -> None:
    aes = AESEncryption()
    encrypted, nonce = aes.encrypt_json({"label": "private"})
    body = dict(
        entity_id="offchain",
        event_type="created",
        details_cid="QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
    )
    if nonce_mode != "omitted":
        body["details_nonce"] = nonce.hex() if nonce_mode == "valid" else None
    response = harness.client.post(
        "/chains/confirmation/events", json=body, headers=harness.headers
    )
    if nonce_mode in ("omitted", "null"):
        assert response.status_code == 422, response.text
        assert harness.persisted() == []
        return
    assert response.status_code == 200, response.text
    assert harness.finished.wait(3)
    rows = harness.persisted()
    assert len(rows) == 1
    assert rows[0]["details_nonce"] == nonce.hex()
    assert aes.decrypt_json(encrypted, bytes.fromhex(rows[0]["details_nonce"])) == {
        "label": "private"
    }


@pytest.mark.parametrize("timeout,repeat", [(0.1, 1), (6.2, 1), (6.2, 2)])
def test_shutdown_worker_resource_order(
    identity: tuple,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    timeout: float,
    repeat: int,
) -> None:
    monkeypatch.chdir(tmp_path)
    waiting = threading.Event()
    original = OrderingProcessor._wait_and_drain_event

    async def observe(self: OrderingProcessor, batch: list[PendingEvent]) -> None:
        waiting.set()
        return await original(self, batch)

    monkeypatch.setattr(OrderingProcessor, "_wait_and_drain_event", observe)
    node, trusted = identity
    service = OrderingService(
        dict(
            chain_name="shutdown",
            db_url=f"sqlite:///{tmp_path / 'shutdown.db'}",
            storage_dir="shutdown-journal",
            batch_timeout=timeout,
            trusted_public_keys=trusted,
        ),
        node_identity=node,
    )
    closed = []
    original_close = service.journal.close

    def observe_close() -> None:
        closed.append(service.processing_thread.is_alive())
        original_close()

    monkeypatch.setattr(service.journal, "close", observe_close)
    try:
        assert waiting.wait(2)
        start = time.monotonic()
        service.shutdown()
        duration = time.monotonic() - start
        alive = service.processing_thread.is_alive()
        assert not alive, (duration, alive)
        assert closed == [False]
        assert duration < 2, (
            "Idle shutdown should not wait for the configured batch timeout"
        )
    finally:
        service.processing_thread.join(timeout=3)
        assert not service.processing_thread.is_alive()
        service.journal.close()


@pytest.mark.parametrize(
    "field",
    ["details", "entity_id", "event", "event_type", "sender", "signature", "nonce"],
)
def test_secure_ordering_binds_signed_content_after_serialization(
    harness: Harness, field: str
) -> None:
    response = harness.client.post(
        "/api/admin/chains/confirmation/secure-events",
        json=secure_body(),
        headers=harness.headers,
    )
    assert response.status_code == 200, response.text
    assert harness.finished.wait(3)
    original = harness.persisted()[0]
    certifier = EventCertifier()

    def certify(data: dict[str, Any]) -> dict[str, Any]:
        event = PendingEvent(
            data["event_id"],
            data,
            "confirmation",
            "recovery",
            time.time(),
            EventStatus.PENDING,
        )
        return certifier.validate(event, allow_stale_timestamp=True)

    assert certify(original)["valid"]
    tampered = copy.deepcopy(original)
    tampered[field] = {"payload": "modified"} if field == "details" else "modified"
    assert not certify(tampered)["valid"]


def test_secure_event_replays_from_journal_before_activation(harness: Harness) -> None:
    old_chain = harness.chain
    old_chain.ordering_service.processor.batch_size = 100
    old_chain.ordering_service.processor.batch_timeout = 60
    old_chain.ordering_service.processor.last_batch_time = time.time()
    response = harness.client.post(
        "/api/admin/chains/confirmation/secure-events",
        json=secure_body(),
        headers=harness.headers,
    )
    assert response.status_code == 200, response.text
    old_chain.shutdown()
    assert not harness.finished.is_set(), (
        "Event must remain journal-only for this recovery test"
    )
    harness.chain = SubChain(
        old_chain.name,
        node_identity=old_chain.node_identity,
        config=old_chain.custom_config,
    )
    assert harness.chain.ordering_service.wait_for_active(3)
    rows = harness.persisted()
    assert len(rows) == 1
    assert rows[0]["event_id"] == response.json()["event_hash"]
    assert rows[0]["details"] == {"payload": "hello"}


def test_secure_queue_backpressure_is_not_reported_as_commit(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full(*args: Any, **kwargs: Any) -> str:
        raise OrderingBackpressureError("full-event", journaled=False)

    monkeypatch.setattr(harness.chain.ordering_service, "receive_event", full)
    response = harness.client.post(
        "/api/admin/chains/confirmation/secure-events",
        json=secure_body(),
        headers=harness.headers,
    )
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["journaled"] is False
    assert harness.persisted() == []
