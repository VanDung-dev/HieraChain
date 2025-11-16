"""
Unit tests for Organization API endpoints in v2

This module contains unit tests for the organization-related endpoints in API v2,
including organization registration.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from hierarchical_blockchain.api.v2.endpoints import register_organization
from hierarchical_blockchain.api.v2.schemas import OrganizationRequest


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
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._organizations', {})
async def test_register_organization_success(mock_org_data):
    """Test successful organization registration"""
    request = OrganizationRequest(**mock_org_data)
    response = await register_organization(request)
    
    assert response.success is True
    assert response.org_id == "manufacturer_org"


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_register_organization_not_implemented(mock_org_data):
    """Test organization registration when modules are not available"""
    request = OrganizationRequest(**mock_org_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await register_organization(request)
    
    # Should raise an HTTPException with status code 501
    assert exc_info.value.status_code == 501