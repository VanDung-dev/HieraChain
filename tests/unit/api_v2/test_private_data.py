"""
Unit tests for Private Data API endpoints in v2

This module contains unit tests for the private data-related endpoints in API v2,
including adding private data to collections.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from api.v2.endpoints import add_private_data
from api.v2.schemas import PrivateDataRequest


@pytest.fixture
def mock_private_data():
    """Mock private data for testing"""
    return {
        "collection": "test_collection",
        "key": "test_key",
        "value": {
            "sensitive_field": "sensitive_value",
            "another_field": 12345
        },
        "event_metadata": {
            "entity_id": "ENTITY-001",
            "event": "contract_negotiation",
            "timestamp": 1717987200.0
        }
    }


@pytest.mark.asyncio
@patch('api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('api.v2.endpoints._private_collections', {"test_collection": {}})
async def test_add_private_data_success(mock_private_data):
    """Test successful addition of private data"""
    request = PrivateDataRequest(**mock_private_data)
    response = await add_private_data(request)
    
    assert response.success is True
    assert response.key == "test_key"


@pytest.mark.asyncio
@patch('api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('api.v2.endpoints._private_collections', {})
async def test_add_private_data_collection_not_found(mock_private_data):
    """Test adding private data to non-existent collection"""
    request = PrivateDataRequest(**mock_private_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await add_private_data(request)
    
    # Should raise an HTTPException with status code 404
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_add_private_data_not_implemented(mock_private_data):
    """Test adding private data when modules are not available"""
    request = PrivateDataRequest(**mock_private_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await add_private_data(request)
    
    # Should raise an HTTPException with status code 501
    assert exc_info.value.status_code == 501