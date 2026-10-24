import json
import os
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

from hierachain.security.security_utils import KeyPair
from hierachain.security.verify.signature_verifier import SignatureVerifier

pytestmark = pytest.mark.docker


@pytest.fixture(params=["sqlite", "postgres", "redis"])
def api(request: pytest.FixtureRequest) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=f"http://app-{request.param}:2661", timeout=20) as client:
        yield client


@pytest.fixture
def keys() -> dict[str, dict[str, str]]:
    path = os.getenv("HRC_CHAIN_CONFIG")
    if not path:
        pytest.skip("Run through docker/scripts/verify_chain_access.py")
    records = json.loads(Path(path).read_text())
    return {record["app_details"]["name"]: {"X-API-Key": key} for key, record in records.items()}


def expect(response: httpx.Response, status: int = 200) -> dict | list:
    assert response.status_code == status, response.text
    return response.json()


def policy(api: httpx.Client, keys: dict, org: str, permissions: list[str]) -> None:
    expect(api.put(f"/api/ledger/chains/access-private/organizations/{org}",
                   headers=keys["platform"], json={"permissions": permissions}))


def events(api: httpx.Client, headers: dict[str, str]) -> httpx.Response:
    return api.post("/graphql", headers=headers, json={
        "query": '{ events(chainName:"access-private") { entityId eventType } }',
    })


def test_live_access(api: httpx.Client, keys: dict) -> None:
    expect(api.get("/api/ledger/chains"), 401)
    for org, member in (("org-a", "alice"), ("org-b", "bob")):
        expect(api.post("/api/business/organizations", headers=keys["platform"], json={"org_id": org, "ca_config": {}}))
        expect(api.post(f"/api/business/organizations/{org}/members", headers=keys["platform"],
                        json={"member_id": member, "role": "member"}))
    for name in ("access-private", "access-public"):
        expect(api.post(f"/api/ledger/chains/{name}/create", headers=keys["platform"]), 201)
    policy(api, keys, "org-a", ["read", "write", "proofs"])
    path = "/api/ledger/chains/access-private"
    expect(api.put(path + "/organizations/org-b", headers=keys["bob"], json={"permissions": ["read"]}), 403)
    expect(api.put(path + "/organizations/org-b", headers=keys["platform"], json={"permissions": []}), 422)
    expect(api.put(path + "/organizations/missing", headers=keys["platform"], json={"permissions": ["read"]}), 404)
    for user in ("bob", "outsider"):
        for suffix in ("blocks", "blocks/0", "stats"):
            expect(api.get(path + "/" + suffix, headers=keys[user]), 403)
        expect(api.post(path + "/events", headers=keys[user],
                        json={"entity_id": "blocked", "event_type": "created"}), 403)
        expect(api.post(path + "/submit-proof", headers=keys[user]), 403)
        expect(api.post("/api/admin/chains/access-private/secure-events", headers=keys[user], json={}), 403)
        expect(events(api, keys[user]), 400)
        listed = expect(api.get("/api/ledger/chains", headers=keys[user]))
        assert "access-private" not in [chain["name"] for chain in listed]
        listed = expect(api.post("/graphql", headers=keys[user], json={"query": "{ allChains { chainName } }"}))
        assert "access-private" not in [chain["chainName"] for chain in listed["data"]["allChains"]]
    payload = {"entity_id": "docker-item", "event_type": "created", "details": {"value": "private"}}
    expect(api.post(path + "/events", headers=keys["reader"], json=payload), 403)
    expect(api.post(path + "/events", headers=keys["alice"], json=payload))
    mutation = {"query": 'mutation { addEvent(event:{chainName:"access-private", entityId:"graphql-item", '
                         'eventType:"created"}) { success } }'}
    expect(api.post("/graphql", headers=keys["bob"], json=mutation), 400)
    assert expect(api.post("/graphql", headers=keys["alice"], json=mutation))["data"]["addEvent"]["success"]
    signer = KeyPair.generate()
    signed = {"entity_id": "secure-item", "event_type": "created", "details": {},
              "sender": "0x" + signer.public_key}
    signed["signature"] = "0x" + signer.sign(SignatureVerifier.get_canonical_bytes(signed))
    expect(api.post("/api/admin/chains/access-private/secure-events", headers=keys["alice"], json=signed))
    deadline = time.monotonic() + 15
    while True:
        blocks = expect(api.get(path + "/blocks", headers=keys["alice"]))["blocks"]
        committed = {event.get("entity_id") for block in blocks for event in block["events"]}
        if {"docker-item", "graphql-item", "secure-item"} <= committed:
            break
        assert time.monotonic() < deadline, "Accepted event did not commit"
        time.sleep(0.1)
    found = expect(events(api, keys["alice"]))["data"]["events"]
    assert any(event["entityId"] == "docker-item" for event in found)
    expect(api.post(path + "/submit-proof", headers=keys["alice"]))
    trace = expect(api.get("/api/ledger/entities/docker-item/trace", headers=keys["bob"]))
    assert not trace["events"]
    expect(api.get(path + "/blocks", headers=keys["alice"]))
    ws_url = str(api.base_url).replace("http://", "ws://").rstrip("/") + "/ws?chain_name=access-private"
    with pytest.raises(InvalidStatus) as error:
        with connect(ws_url, additional_headers=keys["bob"], open_timeout=10):
            pass
    assert error.value.response.status_code == 403
    policy(api, keys, "org-b", ["read"])
    with connect(ws_url, additional_headers=keys["bob"], open_timeout=10) as stream:
        assert json.loads(stream.recv(timeout=10))["type"] == "connected"
        stream.send(json.dumps({"type": "ping"}))
        assert json.loads(stream.recv(timeout=10))["type"] == "pong"
        expect(api.delete(path + "/organizations/org-b", headers=keys["platform"]))
        stream.send(json.dumps({"type": "subscribe", "chain_name": "access-private"}))
        assert json.loads(stream.recv(timeout=10))["type"] == "error"
        stream.send(json.dumps({"type": "get_stats"}))
        assert "access-private" not in json.loads(stream.recv(timeout=10))["data"]["chains"]
    policy(api, keys, "org-a", ["read"])
    expect(api.post(path + "/events", headers=keys["alice"], json=payload), 403)
    expect(api.post(path + "/submit-proof", headers=keys["alice"]), 403)


def test_recovered_access(api: httpx.Client, keys: dict) -> None:
    data = expect(events(api, keys["alice"]))
    assert {"docker-item", "graphql-item", "secure-item"} <= {
        event["entityId"] for event in data["data"]["events"]
    }
    assert expect(api.get("/api/ledger/chains/main_chain/stats", headers=keys["alice"]))["proof_count"] > 0
    expect(events(api, keys["bob"]), 400)
    path = "/api/ledger/chains/access-private"
    saved = expect(api.get(path + "/organizations", headers=keys["platform"]))
    assert saved["managed"] and saved["organizations"] == {"org-a": ["read"]}
    payload = {"entity_id": "blocked", "event_type": "created"}
    expect(api.post(path + "/events", headers=keys["alice"], json=payload), 403)
    expect(api.delete(path + "/organizations/org-a", headers=keys["platform"]))
    expect(api.get(path + "/blocks", headers=keys["alice"]), 403)


def test_empty_policy_survives_recreation(api: httpx.Client, keys: dict) -> None:
    path = "/api/ledger/chains/access-private"
    saved = expect(api.get(path + "/organizations", headers=keys["platform"]))
    assert saved["managed"] and saved["organizations"] == {}
    for user in ("alice", "bob", "outsider"):
        expect(api.get(path + "/blocks", headers=keys[user]), 403)
        expect(events(api, keys[user]), 400)
        expect(api.get("/api/ledger/chains/access-public/blocks", headers=keys[user]))
