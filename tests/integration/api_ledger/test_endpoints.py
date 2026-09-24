"""
Integration tests for API Ledger endpoints
"""

import pytest
from fastapi.testclient import TestClient

from hierachain.api import server


def test_rbac_forbidden_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test protected ledger routes reject requests without an API key."""
    settings = server.get_settings()
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "get_auth_config", lambda: {"enabled": True})
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    auth_client = TestClient(server.create_app())
    try:
        response = auth_client.get("/api/ledger/chains")
        assert response.status_code == 401
        
        response = auth_client.post(
            "/api/ledger/chains/test_chain/events",
            json={"entity_id": "test", "event_type": "test"},
        )
        assert response.status_code == 401
        
        response = auth_client.post("/api/ledger/chains/test_chain/submit-proof")
        assert response.status_code == 401
    finally:
        auth_client.close()


def test_rbac_forbidden_without_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that API ledger endpoints return 403 when API key lacks permissions"""
    settings = server.get_settings()
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "get_auth_config", lambda: {"enabled": True})
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    auth_client = TestClient(server.create_app())
    verifier = auth_client.app.state.auth_verifier
    api_key = verifier.key_manager.create_key("test_user", [])
    try:
        response = auth_client.get(
            "/api/ledger/chains", headers={"x-api-key": api_key}
        )
        assert response.status_code == 403
    finally:
        auth_client.close()
