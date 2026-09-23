"""Regression tests for signed admin event submission."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hierachain.api.admin.endpoints import router
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.security.security_utils import KeyPair
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.security.verify.signature_verifier import SignatureVerifier


def test_secure_event_preserves_signed_fields_and_rejects_tampering() -> None:
    keypair = KeyPair.generate()
    event = {
        "entity_id": "asset-001",
        "event_type": "transfer",
        "details": {"amount": 100},
        "sender": f"0x{keypair.public_key}",
    }
    event["signature"] = f"0x{keypair.sign(SignatureVerifier.get_canonical_bytes(event))}"

    committed: list[dict[str, object]] = []

    class Chain:
        def add_event(self, data: dict[str, object]) -> str:
            committed.append(data)
            return "event-hash"

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
    assert committed == [event]

    tampered = {**event, "details": {"amount": 200}}
    response = client.post("/api/admin/chains/test-chain/secure-events", json=tampered)
    assert response.status_code == 422, response.text
    assert committed == [event]
