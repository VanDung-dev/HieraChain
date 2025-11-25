"""
Unit tests for Channel API endpoints in v2

This module contains unit tests for the channel-related endpoints in API v2,
including channel creation, retrieval, and private collection management.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from hierachain.api.v2.endpoints import create_channel, get_channel, create_private_collection
from hierachain.api.v2.schemas import ChannelCreateRequest, PrivateCollectionCreateRequest


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
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {})
async def test_create_channel_success(mock_channel_data):
    """Test successful channel creation"""
    request = ChannelCreateRequest(**mock_channel_data)
    response = await create_channel(request)
    
    assert response.success is True
    assert response.channel_id == "test_channel"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {})
async def test_create_channel_missing_required_fields():
    """Test channel creation with missing required fields"""
    # Missing channel_id
    invalid_channel_data = {
        "organizations": ["org1", "org2"],
        "policy": {
            "read": "ADMIN || MEMBER",
            "write": "ADMIN"
        }
    }
    
    with pytest.raises(Exception):
        ChannelCreateRequest(**invalid_channel_data)


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {})
async def test_create_channel_empty_values():
    """Test channel creation with empty values"""
    invalid_channel_data = {
        "channel_id": "",  # Empty channel id
        "organizations": [],  # Empty organizations list
        "policy": {}  # Empty policy
    }
    
    request = ChannelCreateRequest(**invalid_channel_data)
    # Current implementation doesn't validate, so this should still succeed
    response = await create_channel(request)
    assert response.success is True
    assert response.channel_id == ""


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {})
async def test_create_channel_invalid_policy():
    """Test channel creation with invalid policy"""
    invalid_channel_data = {
        "channel_id": "invalid_policy_channel",
        "organizations": ["org1", "org2"],
        "policy": {
            "read": "",
            "write": "",  # Invalid empty policy
            "endorsement": "INVALID_POLICY"
        }
    }
    
    request = ChannelCreateRequest(**invalid_channel_data)
    # Depending on implementation, this might still succeed since the current implementation
    # doesn't validate policies. But let's test it anyway for future-proofing
    response = await create_channel(request)
    assert response.success is True
    assert response.channel_id == "invalid_policy_channel"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', False)
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
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {"existing_channel": {}})
async def test_get_channel_success():
    """Test successful channel retrieval"""
    response = await get_channel("existing_channel")
    
    assert response.success is True
    assert response.channel_id == "existing_channel"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {})
async def test_get_channel_not_found():
    """Test channel retrieval for non-existent channel"""
    with pytest.raises(HTTPException) as exc_info:
        await get_channel("non_existent_channel")
    
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {})
async def test_get_channel_edge_cases():
    """Test channel retrieval with edge cases"""
    # Test with empty string
    with pytest.raises(HTTPException) as exc_info:
        await get_channel("")
    
    assert exc_info.value.status_code == 404
    
    # Test with special characters
    with pytest.raises(HTTPException) as exc_info:
        await get_channel("channel with spaces")
    
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {"test_channel": {}})
@patch('hierachain.api.v2.endpoints._private_collections', {})
async def test_create_private_collection_success(mock_collection_data):
    """Test successful private collection creation"""
    request = PrivateCollectionCreateRequest(**mock_collection_data)
    response = await create_private_collection("test_channel", request)
    
    assert response.success is True


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {"test_channel": {}})
@patch('hierachain.api.v2.endpoints._private_collections', {})
async def test_create_private_collection_missing_required_fields():
    """Test private collection creation with missing required fields"""
    # Missing name
    invalid_collection_data = {
        "members": ["org1", "org2"],
        "config": {
            "block_to_purge": 1000,
            "endorsement_policy": "MAJORITY"
        }
    }
    
    with pytest.raises(Exception):
        PrivateCollectionCreateRequest(**invalid_collection_data)


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {"test_channel": {}})
@patch('hierachain.api.v2.endpoints._private_collections', {})
async def test_create_private_collection_empty_values():
    """Test private collection creation with empty values"""
    invalid_collection_data = {
        "name": "",  # Empty name
        "members": [],  # Empty members
        "config": {}  # Empty config
    }
    
    request = PrivateCollectionCreateRequest(**invalid_collection_data)
    # Current implementation doesn't validate, so this should still succeed
    response = await create_private_collection("test_channel", request)
    assert response.success is True


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {"test_channel": {}})
@patch('hierachain.api.v2.endpoints._private_collections', {})
async def test_create_private_collection_invalid_config(mock_collection_data):
    """Test private collection creation with invalid config"""
    invalid_collection_data = {
        "name": "invalid_config_collection",
        "members": ["org1", "org2"],
        "config": {
            "block_to_purge": -1,  # Invalid negative value
            "endorsement_policy": ""  # Invalid empty policy
        }
    }
    
    request = PrivateCollectionCreateRequest(**invalid_collection_data)
    # Depending on implementation, this might still succeed since the current implementation
    # doesn't validate configs. But let's test it anyway for future-proofing
    response = await create_private_collection("test_channel", request)
    assert response.success is True
    assert response.channel_id == "test_channel"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {})
async def test_create_private_collection_channel_not_found(mock_collection_data):
    """Test private collection creation for non-existent channel"""
    request = PrivateCollectionCreateRequest(**mock_collection_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await create_private_collection("non_existent_channel", request)
    
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {"existing_channel": {}})
async def test_create_channel_conflict():
    """Test channel creation when channel already exists"""
    # First create a channel
    channel_data = {
        "channel_id": "existing_channel",
        "organizations": ["org1", "org2"],
        "policy": {
            "read": "ADMIN || MEMBER",
            "write": "ADMIN",
            "endorsement": "MAJORITY"
        }
    }
    
    request = ChannelCreateRequest(**channel_data)
    # The current implementation doesn't prevent duplicates, so this will succeed
    # But we're adding the test for completeness and future implementation
    response = await create_channel(request)
    assert response.success is True
    assert response.channel_id == "existing_channel"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {"test_channel": {}})
async def test_create_private_collection_forbidden_access(mock_collection_data):
    """Test private collection creation with insufficient permissions"""
    # In the current implementation, there's no access control checking
    # But we're adding this test for future implementation
    request = PrivateCollectionCreateRequest(**mock_collection_data)
    response = await create_private_collection("test_channel", request)
    assert response.success is True
    # In a real implementation, this might raise HTTPException with status 403


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._channels', {"test_channel": {}})
async def test_create_private_collection_security_edge_cases(mock_collection_data):
    """Test private collection creation with security edge cases"""
    # Test with unusual but valid data
    edge_case_collection_data = {
        "name": "very_long_collection_name_" * 10,  # Very long name
        "members": ["org1"] * 100,  # Many members
        "config": {
            "block_to_purge": 999999999,  # Very large number
            "endorsement_policy": "ANY"  # Different policy
        }
    }
    
    request = PrivateCollectionCreateRequest(**edge_case_collection_data)
    response = await create_private_collection("test_channel", request)
    assert response.success is True


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_create_private_collection_not_implemented(mock_collection_data):
    """Test private collection creation when modules are not available"""
    request = PrivateCollectionCreateRequest(**mock_collection_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await create_private_collection("test_channel", request)
    
    assert exc_info.value.status_code == 501