"""
Integration tests for API v1 endpoints
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from hierachain.api.server import app
from hierachain.config.settings import Settings

@pytest.fixture
def client():
    """Create a test client for the API"""
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """Return headers with a valid API key"""
    return {"x-api-key": "test_integration_key"}

def test_rbac_forbidden_without_auth(client):
    """Test that API v1 endpoints fail with 401 when missing auth (since it's not configured yet, testing 403 won't work perfectly if not mocked)"""
    with patch.object(Settings, 'AUTH_ENABLED', True):
        response = client.get("/api/v1/chains")
        assert response.status_code == 401
        
        response = client.post("/api/v1/chains/test_chain/events", json={"entity_id": "test", "event_type": "test"})
        assert response.status_code == 401
        
        response = client.post("/api/v1/chains/test_chain/submit-proof")
        assert response.status_code == 401


def test_rbac_forbidden_without_permission(client, auth_headers):
    """Test that API v1 endpoints return 403 when API key lacks permissions"""
    dummy_context = {
        "user_id": "test_user",
        "app_details": {"permissions": []},
    }
    with patch("hierachain.security.verify.api_key_verifier.get_auth_dependency", return_value=dummy_context):
        response = client.get("/api/v1/chains", headers=auth_headers)
        assert response.status_code == 403
