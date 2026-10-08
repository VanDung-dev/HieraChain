"""Regression coverage for GraphQL, WebSocket, and private-data API boundaries."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from hierachain.api import graphql_handler
from hierachain.api.business import state as business_state
from hierachain.api.business.private_data import router as private_data_router
from hierachain.api.graphql_handler import _register_graphql_router
from hierachain.api.ledger import depds
from hierachain.api.websocket.endpoints import router as websocket_router
from hierachain.api.websocket.manager import ws_manager
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier


def _build_authenticated_app(key_manager: KeyManager) -> FastAPI:
    verifier = APIKeyVerifier(
        {
            "enabled": True,
            "key_location": "header",
            "key_name": "X-API-Key",
            "cache_ttl": 0,
        },
        key_manager=key_manager,
    )
    app = FastAPI()
    app.state.auth_verifier = verifier
    _register_graphql_router(app)
    app.include_router(websocket_router)
    return app


def test_graphql_enforces_verified_scope_for_queries_and_mutations(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(HierarchyManager, "_create_storage", staticmethod(lambda: None))
    manager = HierarchyManager()
    request.addfinalizer(manager.transaction_manager.journal.close)
    monkeypatch.setattr(depds, "_hierarchy_manager", manager)

    key_manager = KeyManager()
    chains_key = key_manager.create_key("chain-reader", ["chains"])
    events_key = key_manager.create_key("event-writer", ["events"])
    combined_key = key_manager.create_key("combined-reader", ["chains", "events"])
    app = _build_authenticated_app(key_manager)
    mutation = """
    mutation {
      addEvent(event: {chainName: "main_chain", entityId: "entity-1", eventType: "created"}) {
        success
        error
      }
    }
    """

    with TestClient(app) as client:
        unauthenticated = client.post("/graphql", json={"query": mutation})
        assert unauthenticated.status_code == 401

        denied_mutation = client.post(
            "/graphql", headers={"X-API-Key": chains_key}, json={"query": mutation}
        )
        assert denied_mutation.status_code == 403
        assert manager.main_chain.pending_events == []

        denied_chain_query = client.post(
            "/graphql",
            headers={"X-API-Key": events_key},
            json={"query": "{ allChains { chainName } }"},
        )
        assert denied_chain_query.status_code == 403

        denied_nested_event_query = client.post(
            "/graphql",
            headers={"X-API-Key": chains_key},
            json={"query": "{ blocks(chainName: \"main_chain\") { events { entityId } } }"},
        )
        assert denied_nested_event_query.status_code == 403

        allowed_chain_query = client.post(
            "/graphql",
            headers={"X-API-Key": chains_key},
            json={"query": "{ allChains { chainName } }"},
        )
        assert allowed_chain_query.status_code == 200
        assert allowed_chain_query.json()["data"]["allChains"]

        allowed_event_query = client.post(
            "/graphql",
            headers={"X-API-Key": events_key},
            json={"query": "{ events(chainName: \"main_chain\", limit: 1) { entityId } }"},
        )
        assert allowed_event_query.status_code == 200
        assert allowed_event_query.json()["data"]["events"] == [{"entityId": "SYSTEM"}]

        nested_query = client.post(
            "/graphql", headers={"X-API-Key": combined_key},
            json={"query": '{ blocks(chainName: "main_chain", limit: 1) '
                           '{ index events { entityId eventType details } } }'},
        )
        assert nested_query.status_code == 200
        row = nested_query.json()["data"]["blocks"][0]["events"][0]
        assert row["entityId"] == "SYSTEM"
        assert row["eventType"] == "genesis"
        assert row["details"]


        allowed_mutation = client.post(
            "/graphql", headers={"X-API-Key": events_key}, json={"query": mutation}
        )
        assert allowed_mutation.status_code == 200
        assert allowed_mutation.json()["data"]["addEvent"]["success"] is True
        assert len(manager.main_chain.pending_events) == 1

        unknown_mutation = client.post(
            "/graphql", headers={"X-API-Key": events_key},
            json={"query": mutation.replace("main_chain", "missing-chain")},
        )
        assert unknown_mutation.json()["data"]["addEvent"]["success"] is False
        assert len(manager.main_chain.pending_events) == 1
        unknown_query = client.post(
            "/graphql", headers={"X-API-Key": events_key},
            json={"query": '{ events(chainName: "missing-chain") { entityId } }'},
        )
        assert unknown_query.json()["data"]["events"] == []



def test_websocket_requires_scopes_for_combined_chain_and_event_streams() -> None:
    key_manager = KeyManager()
    chains_key = key_manager.create_key("chain-reader", ["chains"])
    events_key = key_manager.create_key("event-reader", ["events"])
    stream_key = key_manager.create_key("stream-reader", ["chains", "events"])
    app = _build_authenticated_app(key_manager)

    with TestClient(app) as client:
        starting_connections = ws_manager.connection_count
        assert client.get("/ws/status", headers={"X-API-Key": events_key}).status_code == 403
        assert client.get("/ws/status", headers={"X-API-Key": chains_key}).status_code == 200
        for api_key in (chains_key, events_key):
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(
                    "/ws?chain_name=main_chain", headers={"X-API-Key": api_key}
                ):
                    pass
            assert ws_manager.connection_count == starting_connections

        with client.websocket_connect(
            "/ws?chain_name=main_chain", headers={"X-API-Key": stream_key}
        ) as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"
            websocket.send_json({
                "type": "subscribe",
                "chain_name": "main_chain",
                "event_types": ["created"],
            })
            assert websocket.receive_json()["type"] == "subscribed"
            assert connected["connection_id"] in ws_manager.chain_subscribers["main_chain"]


def test_websocket_still_allows_connections_when_authentication_is_disabled() -> None:
    app = FastAPI()
    app.include_router(websocket_router)

    with TestClient(app) as client:
        with client.websocket_connect("/ws?chain_name=main_chain") as websocket:
            assert websocket.receive_json()["type"] == "connected"


def test_enabled_auth_fails_closed_when_transport_has_no_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRC_ENV", "production")
    monkeypatch.setenv("HRC_AUTH_ENABLED", "true")
    monkeypatch.setattr(graphql_handler.graphql_security, "check_rate_limit", lambda _ip: True)
    app = FastAPI()
    _register_graphql_router(app)
    app.include_router(websocket_router)

    with TestClient(app) as client:
        response = client.post("/graphql", json={"query": "{ allChains { chainName } }"})
        assert response.status_code == 503
        assert client.get("/ws/status").status_code == 401

        starting_connections = ws_manager.connection_count
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws"):
                pass
        assert ws_manager.connection_count == starting_connections


@pytest.mark.parametrize(
    "value_fields",
    [
        {"value": {"text": "private payload"}},
        {
            "value_cid": "Qm" + "1" * 44,
            "value_nonce": "a1" * 12,
            "value_metadata": {"collection": "test-private-collection"},
        },
    ],
)
def test_private_data_fails_closed_before_processing_inline_or_cid_values(
    monkeypatch: pytest.MonkeyPatch,
    value_fields: dict[str, object],
) -> None:
    collection = "test-private-collection"
    marker = object()
    monkeypatch.setitem(business_state._private_collections, collection, marker)
    app = FastAPI()
    app.include_router(private_data_router)
    request_data = {
        "collection": collection,
        "key": "private-record-1",
        "event_metadata": {
            "entity_id": "entity-1",
            "event": "record_created",
            "timestamp": 1717987200.0,
        },
        **value_fields,
    }

    with TestClient(app) as client:
        response = client.post("/private-data", json=request_data)

    assert response.status_code == 501
    assert response.json()["detail"] == "Private-data storage is not implemented."
    assert business_state._private_collections[collection] is marker
