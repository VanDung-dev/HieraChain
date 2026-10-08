"""Business API health and authentication boundary tests."""

import pytest
from fastapi.testclient import TestClient

from hierachain.api import app, server


@pytest.fixture
def client():
    """Create a test client for the API"""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Return headers with a valid API key"""
    return {"x-api-key": "test_integration_key"}


def test_api_business_health_check(client, auth_headers):
    """Test API business health check endpoint"""
    response = client.get("/api/business/health", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "business"


def test_create_channel_requires_management_scope(client, auth_headers):
    """A regular API key cannot provision channels."""
    channel_data = {
        "channel_id": "integration_test_channel",
        "organizations": ["org1", "org2", "org3"],
        "policy": {
            "read": "MEMBER",
            "write": "ADMIN",
            "endorsement": "MAJORITY"
        }
    }
    
    response = client.post("/api/business/channels", json=channel_data, headers=auth_headers)
    assert response.status_code in (401, 403)


def test_register_organization_requires_management_scope(client, auth_headers):
    """A regular API key cannot provision organizations."""
    org_data = {
        "org_id": "manufacturer_org",
        "ca_config": {
            "root_cert": "-----BEGIN CERTIFICATE-----...",
            "intermediate_certs": ["-----BEGIN CERTIFICATE-----..."],
            "policy": {
                "certificate_lifetimes": {
                    "root": 3650,
                    "intermediate": 1825,
                    "entity": 365
                }
            }
        }
    }
    
    response = client.post("/api/business/organizations", json=org_data, headers=auth_headers)
    assert response.status_code in (401, 403)

def test_rbac_forbidden_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that requests fail with 401 when missing auth"""
    settings = server.get_settings()
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "get_auth_config", lambda: {"enabled": True})
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    auth_client = TestClient(server.create_app())
    try:
        response = auth_client.post(
            "/api/business/channels",
            json={"channel_id": "test", "organizations": [], "policy": {}},
        )
        assert response.status_code == 401
        
        response = auth_client.post(
            "/api/business/contracts",
            json={"contract_id": "test", "version": "1", "implementation": ""},
        )
        assert response.status_code == 401
    finally:
        auth_client.close()
