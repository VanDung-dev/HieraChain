from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from hierachain.api import graphql_handler
from hierachain.api.admin.endpoints import router as admin_router
from hierachain.api.ledger import depds
from hierachain.api.ledger.router import ledger_router
from hierachain.api.websocket.endpoints import router as websocket_router
from hierachain.api.websocket.manager import ws_manager
from hierachain.core.block import Block
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier


@pytest.fixture
def setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> Iterator[tuple[FastAPI, HierarchyManager, dict[str, dict[str, str]]]]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    manager.create_organization("org-a", "A", ["alice"])
    manager.create_organization("org-b", "B", ["bob"])
    for name in ("private", "public"):
        block = Block(0, [{"entity_id": "item", "event": "created", "timestamp": 1.0,
                           "details": {"value": name}}], previous_hash="0")
        manager.sub_chains[name] = SimpleNamespace(
            name=name, chain=[block], get_latest_block=lambda block=block: block,
            add_event=Mock(return_value="accepted"), shutdown=Mock(),
        )
    assert manager.assign_organization_to_chain("org-a", "private", permissions=["read", "write", "proofs"])
    monkeypatch.setattr(depds, "_hierarchy_manager", manager)
    monkeypatch.setattr(graphql_handler.graphql_security, "check_rate_limit", lambda _ip: True)
    keys = KeyManager()
    headers = {
        user: {"X-API-Key": keys.create_key(user, permissions)}
        for user, permissions in (
            ("alice", ["chains", "events", "proofs"]),
            ("bob", ["chains", "events", "proofs"]),
            ("outsider", ["all"]),
            ("platform", ["chains", "chains:manage"]),
            ("reader", ["chains"]),
        )
    }
    app = FastAPI()
    app.state.auth_verifier = APIKeyVerifier({"enabled": True}, key_manager=keys)
    app.dependency_overrides[depds.get_hierarchy_manager] = lambda: manager
    tracer = SimpleNamespace(trace_entity_in_chain=lambda entity, name: {
        "events": [{"chain": name, "entity_id": entity}],
    })
    app.dependency_overrides[depds.get_entity_tracer] = lambda: tracer
    app.include_router(ledger_router)
    app.include_router(admin_router)
    app.include_router(websocket_router)
    graphql_handler._register_graphql_router(app)
    yield app, manager, headers
    manager.close()


@pytest.mark.parametrize("suffix", ["blocks", "blocks/0", "stats", "create", "submit-proof"])
def test_denied_rest_paths(setup: tuple, suffix: str) -> None:
    app, _manager, headers = setup
    with TestClient(app) as client:
        method = client.post if suffix in {"create", "submit-proof"} else client.get
        assert method(f"/api/ledger/chains/private/{suffix}", headers=headers["bob"]).status_code == 403


def test_rest_reads_writes_and_scope_intersection(setup: tuple) -> None:
    app, manager, headers = setup
    payload = {"entity_id": "item", "event_type": "created", "details": {}}
    with TestClient(app) as client:
        assert client.get("/api/ledger/chains/private/blocks", headers=headers["alice"]).status_code == 200
        assert client.post("/api/admin/chains/private/secure-events", json={},
                           headers=headers["bob"]).status_code == 403
        for user in ("bob", "outsider"):
            assert client.post("/api/ledger/chains/private/events", json=payload,
                               headers=headers[user]).status_code == 403
        assert client.post("/api/ledger/chains/private/events", json=payload,
                           headers=headers["alice"]).status_code == 200
        assert client.post("/api/ledger/chains/public/events", json=payload,
                           headers=headers["reader"]).status_code == 403
        assert client.post("/api/ledger/chains/public/events", json=payload, headers=headers["bob"]).status_code == 200
        assert manager.assign_organization_to_chain("org-a", "private", permissions=["read"])
        assert client.post("/api/ledger/chains/private/events", json=payload,
                           headers=headers["alice"]).status_code == 403
    assert manager.sub_chains["private"].add_event.call_count == 1


def test_disabled_authentication_cannot_bypass_managed_chain(setup: tuple) -> None:
    app, _manager, _headers = setup
    app.state.auth_verifier = None
    with TestClient(app) as client:
        assert client.get("/api/ledger/chains/public/blocks").status_code == 200
        assert client.get("/api/ledger/chains/private/blocks").status_code == 403
        assert client.put("/api/ledger/chains/private/organizations/org-b",
                          json={"permissions": ["read"]}).status_code == 403


def test_lists_and_cross_chain_trace_filter_private_chain(setup: tuple) -> None:
    app, _manager, headers = setup
    with TestClient(app) as client:
        names = [entry["name"] for entry in client.get("/api/ledger/chains", headers=headers["bob"]).json()]
        assert "private" not in names and "public" in names
        result = client.get("/api/ledger/entities/item/trace", headers=headers["bob"])
        assert result.status_code == 200
        assert result.json()["chains"] == ["public"]
        assert client.get("/api/ledger/entities/item/trace?chain_name=private",
                          headers=headers["bob"]).status_code == 403


def test_management_and_last_revocation(setup: tuple) -> None:
    app, manager, headers = setup
    path = "/api/ledger/chains/private/organizations/org-b"
    with TestClient(app) as client:
        assert client.put(path, json={"permissions": ["read"]}, headers=headers["bob"]).status_code == 403
        for invalid in ([], ["all"]):
            assert client.put(path, json={"permissions": invalid}, headers=headers["platform"]).status_code == 422
        assert client.put(path, json={"permissions": ["read"]}, headers=headers["platform"]).status_code == 200
        assert client.get("/api/ledger/chains/private/blocks", headers=headers["bob"]).status_code == 200
        assert client.delete(path, headers=headers["platform"]).status_code == 200
        assert client.get("/api/ledger/chains/private/blocks", headers=headers["bob"]).status_code == 403
        assert client.delete(path.replace("org-b", "org-a"), headers=headers["platform"]).status_code == 200
        policy = client.get("/api/ledger/chains/private/organizations", headers=headers["platform"]).json()
        assert policy["managed"] is True and policy["organizations"] == {}
        assert not manager.can_access_chain("private", "alice", "read")


@pytest.mark.parametrize("query", [
    '{ blocks(chainName:"private") { index } }',
    '{ block(chainName:"private", blockIndex:0) { index } }',
    '{ events(chainName:"private") { entityId } }',
    '{ chainStatus(chainName:"private") { chainName } }',
    'mutation { addEvent(event:{chainName:"private", entityId:"item", eventType:"created"}) { success } }',
])
def test_graphql_named_queries_and_mutations_are_scoped(setup: tuple, query: str) -> None:
    app, manager, headers = setup
    with TestClient(app) as client:
        denied = client.post("/graphql", json={"query": query}, headers=headers["bob"])
        assert denied.status_code == 400 and denied.json()["errors"]
        allowed = client.post("/graphql", json={"query": query}, headers=headers["alice"])
        assert allowed.status_code == 200, allowed.text
    if "mutation" in query:
        assert manager.sub_chains["private"].add_event.call_count == 1


def test_graphql_all_chains_filters_results(setup: tuple) -> None:
    app, _manager, headers = setup
    with TestClient(app) as client:
        data = client.post("/graphql", json={"query": "{ allChains { chainName } }"}, headers=headers["bob"]).json()
        names = [entry["chainName"] for entry in data["data"]["allChains"]]
        assert "private" not in names and "public" in names


def test_websocket_subscription_and_live_revocation(setup: tuple) -> None:
    app, manager, headers = setup
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws?chain_name=private", headers=headers["bob"]):
                pass
        with client.websocket_connect("/ws", headers=headers["alice"]) as alice:
            alice.receive_json()
            with client.websocket_connect("/ws", headers=headers["bob"]) as bob:
                bob.receive_json()
                bob.send_json({"type": "subscribe", "chain_name": "private"})
                assert bob.receive_json()["type"] == "error"
                message = {"type": "event", "chain_name": "private", "data": {"secret": 1}}
                client.portal.call(ws_manager.broadcast_to_all, message)
                assert alice.receive_json()["data"] == {"secret": 1}
                bob.send_json({"type": "ping", "timestamp": 1})
                assert bob.receive_json()["type"] == "pong"
                assert manager.revoke_organization_from_chain("org-a", "private")
                client.portal.call(ws_manager.broadcast_to_all, message)
                alice.send_json({"type": "ping", "timestamp": 2})
                assert alice.receive_json()["type"] == "pong"


def test_existing_websocket_observes_first_assignment_and_backend_failure(
    setup: tuple, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, manager, headers = setup
    with TestClient(app) as client:
        with client.websocket_connect("/ws?chain_name=public", headers=headers["bob"]) as bob:
            bob.receive_json()
            bob.send_json({"type": "subscribe", "chain_name": "public", "event_types": ["created"]})
            assert bob.receive_json()["type"] == "subscribed"
            message = {"type": "event", "chain_name": "public", "data": {"value": 1}}
            client.portal.call(ws_manager.broadcast_to_event_type, "public", "created", message)
            assert bob.receive_json()["data"] == {"value": 1}
            assert manager.assign_organization_to_chain("org-a", "public", permissions=["read"])
            client.portal.call(ws_manager.broadcast_to_chain, "public", message)
            client.portal.call(ws_manager.broadcast_to_event_type, "public", "created", message)
            bob.send_json({"type": "ping"})
            assert bob.receive_json()["type"] == "pong"
            assert "public" not in client.get("/ws/status", headers=headers["bob"]).json()["stats"]["chains"]
            assert manager.assign_organization_to_chain("org-b", "public", permissions=["read"])

            def unavailable(*_args: object) -> bool:
                raise RuntimeError("backend unavailable")

            monkeypatch.setattr(manager, "can_access_chain", unavailable)
            client.portal.call(ws_manager.broadcast_to_chain, "public", message)
            bob.send_json({"type": "ping"})
            assert bob.receive_json()["type"] == "pong"
