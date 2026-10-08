"""Regression tests for signed admin event submission."""

import threading
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.api.admin.endpoints import router
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.core.utils import validate_event_structure
from hierachain.hierarchical.sub_chain import SubChain
from hierachain.security.security_utils import KeyPair
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.security.verify.signature_verifier import SignatureVerifier


def test_secure_event_preserves_signed_fields_and_rejects_tampering() -> None:
    keypair = KeyPair.generate()
    event = {
        "entity_id": "asset-001",
        "event_type": "transfer",
        "details": {"value": 100},
        "sender": f"0x{keypair.public_key}",
    }
    event["signature"] = f"0x{keypair.sign(SignatureVerifier.get_canonical_bytes(event))}"

    committed: list[dict[str, object]] = []

    class Chain:
        # Exercise the real SubChain validation/queue path, without starting a backend.
        name = "test-chain"
        lock = threading.RLock()
        pending_events = committed
        ordering_service = Mock()
        ordering_service.receive_event.return_value = "event-hash"
        add_event = SubChain.add_event

    class Manager:
        def get_sub_chain(self, name: str) -> Chain | None:
            return Chain() if name == "test-chain" else None

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_hierarchy_manager] = Manager
    app.dependency_overrides[require_chain_access] = lambda: None
    client = TestClient(app)

    response = client.post("/api/admin/chains/test-chain/secure-events", json=event)
    assert response.status_code == 200, response.text
    assert len(committed) == 1
    assert all(committed[0][key] == value for key, value in event.items())
    Chain.ordering_service.receive_event.assert_called_once()

    tampered = {**event, "details": {"value": 200}}
    response = client.post("/api/admin/chains/test-chain/secure-events", json=tampered)
    assert response.status_code == 422, response.text
    assert len(committed) == 1
    Chain.ordering_service.receive_event.assert_called_once()


def test_signed_envelope_does_not_exempt_nested_business_terms() -> None:
    event = {"entity_id": "e", "event": "created", "timestamp": 1, "sender": "0x" + "ab" * 32}
    assert validate_event_structure(event)
    assert not validate_event_structure({**event, "details": {"sender": "person"}})
    assert not validate_event_structure({**event, "details": {"amount": 1}})
    assert not validate_event_structure({**event, "sender": "wallet"})
