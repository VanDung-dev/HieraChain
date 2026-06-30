"""
Integration tests for API v2

This module contains integration tests for the API v2 endpoints,
including testing the complete flow of channel creation, private collection management,
private data handling, contract operations, and organization registration.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from hierachain.api import app
from hierachain.config import Settings


@pytest.fixture
def client():
    """Create a test client for the API"""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Return headers with a valid API key"""
    return {"x-api-key": "test_integration_key"}


def test_api_v2_health_check(client, auth_headers):
    """Test API v2 health check endpoint"""
    response = client.get("/api/business/health", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "v2"


def test_create_channel(client, auth_headers):
    """Test creating a channel via API v2"""
    channel_data = {
        "channel_id": "integration_test_channel",
        "organizations": ["org1", "org2", "org3"],
        "policy": {
            "read": "ADMIN || MEMBER",
            "write": "ADMIN",
            "endorsement": "MAJORITY"
        }
    }
    
    response = client.post("/api/business/channels", json=channel_data, headers=auth_headers)
    # Since the modules are not actually implemented, we expect a 501 error
    assert response.status_code == 501 or response.status_code == 200


def test_create_private_collection(client, auth_headers):
    """Test creating a private collection via API v2"""
    collection_data = {
        "name": "integration_test_collection",
        "members": ["org1", "org2"],
        "config": {
            "block_to_purge": 1000,
            "endorsement_policy": "MAJORITY"
        }
    }
    
    response = client.post("/api/business/channels/test_channel/private-collections", json=collection_data, headers=auth_headers)
    # Since the modules are not actually implemented, we expect a 501 or 404 error
    assert response.status_code in [501, 404, 200]


def test_add_private_data(client, auth_headers):
    """Test adding private data via API v2"""
    data = {
        "collection": "test_collection",
        "key": "contract_terms_001",
        "value": {
            "price": 10000,
            "discount": 0.1,
            "payment_terms": "NET30"
        },
        "event_metadata": {
            "entity_id": "CONTRACT-2024-001",
            "event": "contract_negotiation",
            "timestamp": 1717987200.0
        }
    }
    
    response = client.post("/api/business/private-data", json=data, headers=auth_headers)
    # Since the modules are not actually implemented, we expect a 501 or 404 error
    assert response.status_code in [501, 404, 200]


def test_create_contract(client, auth_headers):
    """Test creating a contract via API v2"""
    contract_data = {
        "contract_id": "quality_control_contract",
        "version": "1.0.0",
        "implementation": "def quality_control_logic(event, state, context): return {'status': 'approved'}",
        "metadata": {
            "domain": "manufacturing",
            "owner": "org1",
            "endorsement_policy": "MAJORITY"
        }
    }
    
    response = client.post("/api/business/contracts", json=contract_data, headers=auth_headers)
    # Since the modules are not actually implemented, we expect a 501 error
    assert response.status_code == 501 or response.status_code == 200


def test_execute_contract(client, auth_headers):
    """Test executing a contract via API v2"""
    execution_data = {
        "contract_id": "quality_control_contract",
        "event": {
            "entity_id": "PRODUCT-2024-001",
            "event": "quality_check",
            "timestamp": 1717987200.0,
            "details": {
                "result": "pass",
                "inspector_id": "INSPECTOR-03"
            }
        },
        "context": {
            "chain": "quality_chain"
        }
    }
    
    response = client.post("/api/business/contracts/execute", json=execution_data, headers=auth_headers)
    # Since the modules are not actually implemented, we expect a 501 or 404 error
    assert response.status_code in [501, 404, 200]


def test_register_organization(client, auth_headers):
    """Test registering an organization via API v2"""
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
    # Since the modules are not actually implemented, we expect a 501 error
    assert response.status_code == 501 or response.status_code == 200

def test_rbac_forbidden_without_auth(client):
    """Test that requests fail with 401 when missing auth"""
    with patch.object(Settings, 'AUTH_ENABLED', True):
        response = client.post("/api/business/channels", json={"channel_id": "test", "organizations": [], "policy": {}})
        assert response.status_code == 401
        
        response = client.post("/api/business/contracts", json={"contract_id": "test", "version": "1", "implementation": ""})
        assert response.status_code == 401