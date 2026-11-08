"""Regression coverage for WebSocket API boundaries."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import HTTPConnection, Request
from starlette.types import Scope
from starlette.websockets import WebSocket, WebSocketDisconnect

from hierachain.api.websocket.endpoints import router as websocket_router
from hierachain.api.websocket.manager import ws_manager
from hierachain.security.key_manager import KeyManager
from hierachain.security.verify.api_key_verifier import APIKeyVerifier


@pytest.mark.asyncio
@pytest.mark.parametrize("connection_type", [Request, WebSocket])
@pytest.mark.parametrize("location", ["header", "query"])
async def test_api_key_extraction_for_both_transports(
    connection_type: type[HTTPConnection], location: str,
) -> None:
    verifier = APIKeyVerifier({"key_location": location, "key_name": "X-API-Key"})
    scope: Scope = {
        "type": "http" if connection_type is Request else "websocket",
        "headers": [(b"x-api-key", b"header-value")],
        "query_string": b"X-API-Key=query-value",
    }
    connection = (
        WebSocket(scope, AsyncMock(), AsyncMock())
        if connection_type is WebSocket else Request(scope)
    )
    assert await verifier._extract_api_key(connection, None) == f"{location}-value"
    assert await verifier._extract_api_key(connection, "explicit-value") == "explicit-value"


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
    app.include_router(websocket_router)
    return app


def test_websocket_requires_scopes_for_combined_chain_and_event_streams(
    isolated_api_hierarchy: None,
) -> None:
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


def test_websocket_still_allows_connections_when_authentication_is_disabled(
    isolated_api_hierarchy: None,
) -> None:
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
    app = FastAPI()
    app.include_router(websocket_router)

    with TestClient(app) as client:
        assert client.get("/ws/status").status_code == 401

        starting_connections = ws_manager.connection_count
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws"):
                pass
        assert ws_manager.connection_count == starting_connections
