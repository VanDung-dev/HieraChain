"""
Unit tests for Channel API endpoints in v2

This module contains unit tests for the channel-related endpoints in API v2,
including channel creation, retrieval, and private collection management.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from hierarchical_blockchain.api.v2.endpoints import create_channel, get_channel, create_private_collection
from hierarchical_blockchain.api.v2.schemas import ChannelCreateRequest, PrivateCollectionCreateRequest


@pytest.fixture
def mock_channel_data():
    """Mock channel data for testing"""
    return {
        "channel_id": "test_channel",
        "organizations": ["org1", "org2"],
        "policy": {
            "read": "ADMIN || MEMBER",
            "write": "ADMIN",
            "endorsement": "MAJORITY"
        }
    }


@pytest.fixture
def mock_collection_data():
    """Mock private collection data for testing"""
    return {
        "name": "test_collection",
        "members": ["org1", "org2"],
        "config": {
            "block_to_purge": 1000,
            "endorsement_policy": "MAJORITY"
        }
    }


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._channels', {})
async def test_create_channel_success(mock_channel_data):
    """Test successful channel creation"""
    request = ChannelCreateRequest(**mock_channel_data)
    response = await create_channel(request)
    
    assert response.success is True
    assert response.channel_id == "test_channel"


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_create_channel_not_implemented():
    """Test channel creation when modules are not available"""
    request = ChannelCreateRequest(
        channel_id="test_channel",
        organizations=["org1", "org2"],
        policy={"read": "ADMIN"}
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await create_channel(request)
    
    assert exc_info.value.status_code == 501


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._channels', {"existing_channel": {}})
async def test_get_channel_success():
    """Test successful channel retrieval"""
    response = await get_channel("existing_channel")
    
    assert response.success is True
    assert response.channel_id == "existing_channel"


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._channels', {})
async def test_get_channel_not_found():
    """Test channel retrieval for non-existent channel"""
    with pytest.raises(HTTPException) as exc_info:
        await get_channel("non_existent_channel")
    
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._channels', {"test_channel": {}})
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {})
async def test_create_private_collection_success(mock_collection_data):
    """Test successful private collection creation"""
    request = PrivateCollectionCreateRequest(**mock_collection_data)
    response = await create_private_collection("test_channel", request)
    
    assert response.success is True


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._channels', {})
async def test_create_private_collection_channel_not_found(mock_collection_data):
    """Test private collection creation for non-existent channel"""
    request = PrivateCollectionCreateRequest(**mock_collection_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await create_private_collection("non_existent_channel", request)
    
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_create_private_collection_not_implemented(mock_collection_data):
    """Test private collection creation when modules are not available"""
    request = PrivateCollectionCreateRequest(**mock_collection_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await create_private_collection("test_channel", request)
    
    assert exc_info.value.status_code == 501