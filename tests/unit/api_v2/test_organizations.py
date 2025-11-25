"""
Unit tests for Organization API endpoints in v2

This module contains unit tests for the organization-related endpoints in API v2,
including organization registration.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from hierachain.api.v2.endpoints import register_organization
from hierachain.api.v2.schemas import OrganizationRequest


@pytest.fixture
def mock_org_data():
    """Mock organization data for testing"""
    return {
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


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._organizations', {})
async def test_register_organization_success(mock_org_data):
    """Test successful organization registration"""
    request = OrganizationRequest(**mock_org_data)
    response = await register_organization(request)
    
    assert response.success is True
    assert response.org_id == "manufacturer_org"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._organizations', {})
async def test_register_organization_missing_required_fields():
    """Test organization registration with missing required fields"""
    # Missing org_id
    invalid_org_data = {
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
    
    with pytest.raises(Exception):
        OrganizationRequest(**invalid_org_data)


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._organizations', {})
async def test_register_organization_empty_values():
    """Test organization registration with empty values"""
    invalid_org_data = {
        "org_id": "",  # Empty org id
        "ca_config": {}  # Empty ca config
    }
    
    request = OrganizationRequest(**invalid_org_data)
    # Current implementation doesn't validate, so this should still succeed
    response = await register_organization(request)
    assert response.success is True
    assert response.org_id == ""


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._organizations', {})
async def test_register_organization_invalid_ca_config():
    """Test organization registration with invalid CA config"""
    invalid_org_data = {
        "org_id": "invalid_ca_org",
        "ca_config": {
            "root_cert": "",  # Empty certificate
            "intermediate_certs": [],
            "policy": {}  # Missing policy
        }
    }
    
    request = OrganizationRequest(**invalid_org_data)
    # Current implementation doesn't validate, so this should still succeed
    response = await register_organization(request)
    assert response.success is True
    assert response.org_id == "invalid_ca_org"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._organizations', {"existing_org": {}})
async def test_register_organization_already_exists(mock_org_data):
    """Test organization registration when organization already exists"""
    request = OrganizationRequest(**mock_org_data)
    # Change org_id to existing one
    request.org_id = "existing_org"
    
    # Current implementation doesn't check for duplicates, so this should still succeed
    response = await register_organization(request)
    assert response.success is True
    assert response.org_id == "existing_org"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._organizations', {})
async def test_register_organization_invalid_certificate_policy():
    """Test organization registration with invalid certificate policy"""
    invalid_org_data = {
        "org_id": "invalid_policy_org",
        "ca_config": {
            "root_cert": "-----BEGIN CERTIFICATE-----...",
            "intermediate_certs": ["-----BEGIN CERTIFICATE-----..."],
            "policy": {
                "certificate_lifetimes": {
                    "root": -1,  # Invalid negative lifetime
                    "intermediate": 0,  # Invalid zero lifetime
                    "entity": -365  # Invalid negative lifetime
                }
            }
        }
    }
    
    request = OrganizationRequest(**invalid_org_data)
    # Current implementation doesn't validate, so this should still succeed
    response = await register_organization(request)
    assert response.success is True
    assert response.org_id == "invalid_policy_org"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._organizations', {})
async def test_register_organization_security_edge_cases():
    """Test organization registration with security edge cases"""
    edge_case_org_data = {
        "org_id": "very_long_org_id_" * 20,  # Very long org id
        "ca_config": {
            "root_cert": "-----BEGIN CERTIFICATE-----" + "A" * 10000 + "-----END CERTIFICATE-----",
            "intermediate_certs": ["-----BEGIN CERTIFICATE-----" + "B" * 5000 + "-----END CERTIFICATE-----"] * 10,
            "policy": {
                "certificate_lifetimes": {
                    "root": 999999,
                    "intermediate": 999999,
                    "entity": 999999
                }
            }
        }
    }
    
    request = OrganizationRequest(**edge_case_org_data)
    response = await register_organization(request)
    assert response.success is True
    assert response.org_id == edge_case_org_data["org_id"]


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_register_organization_not_implemented(mock_org_data):
    """Test organization registration when modules are not available"""
    request = OrganizationRequest(**mock_org_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await register_organization(request)
    
    # Should raise an HTTPException with status code 501
    assert exc_info.value.status_code == 501