"""
Unit tests for Private Data API endpoints in v2

This module contains unit tests for the private data-related endpoints in API v2,
including adding private data to collections.
"""

import asyncio
import time
import pytest
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError

from hierarchical_blockchain.api.v2.endpoints import add_private_data
from hierarchical_blockchain.api.v2.schemas import PrivateDataRequest


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
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
async def test_add_private_data_success(mock_private_data):
    """Test successful addition of private data"""
    request = PrivateDataRequest(**mock_private_data)
    response = await add_private_data(request)
    
    assert response.success is True
    assert response.key == "test_key"


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {})
async def test_add_private_data_collection_not_found(mock_private_data):
    """Test adding private data to non-existent collection"""
    request = PrivateDataRequest(**mock_private_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await add_private_data(request)
    
    # Should raise an HTTPException with status code 404
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_add_private_data_not_implemented(mock_private_data):
    """Test adding private data when modules are not available"""
    request = PrivateDataRequest(**mock_private_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await add_private_data(request)
    
    # Should raise an HTTPException with status code 501
    assert exc_info.value.status_code == 501


# Test cases for invalid data
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
def test_add_private_data_null_collection():
    """Test adding private data with null collection name"""
    with pytest.raises(ValidationError):
        PrivateDataRequest(
            collection=None,
            key="test_key",
            value={"field": "value"},
            event_metadata={
                "entity_id": "ENTITY-001",
                "event": "contract_negotiation",
                "timestamp": 1717987200.0
            }
        )


@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
def test_add_private_data_invalid_value_format():
    """Test adding private data with invalid value format"""
    with pytest.raises(ValidationError):
        PrivateDataRequest(
            collection="test_collection",
            key="test_key",
            value=[],  # This should fail validation as it's not a dict
            event_metadata={
                "entity_id": "ENTITY-001",
                "event": "contract_negotiation",
                "timestamp": 1717987200.0
            }
        )


# Test cases for edge cases
@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
async def test_add_private_data_empty_strings():
    """Test adding private data with empty strings for collection and key"""
    # Empty strings are valid according to the schema, so we test the endpoint behavior
    request = PrivateDataRequest(
        collection="",
        key="",
        value={"field": "value"},
        event_metadata={
            "entity_id": "ENTITY-001",
            "event": "contract_negotiation",
            "timestamp": 1717987200.0
        }
    )
    
    # With empty collection, should get 404 since it won't be found
    with pytest.raises(HTTPException) as exc_info:
        await add_private_data(request)
    
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
async def test_add_private_data_special_characters_key():
    """Test adding private data with special characters in key"""
    request = PrivateDataRequest(
        collection="test_collection",
        key="special!@#$%^&*()_+-={}[]|\\:;\"'<>?,./key",
        value={"field": "value"},
        event_metadata={
            "entity_id": "ENTITY-001",
            "event": "contract_negotiation",
            "timestamp": 1717987200.0
        }
    )
    
    response = await add_private_data(request)
    assert response.success is True
    assert response.key == "special!@#$%^&*()_+-={}[]|\\:;\"'<>?,./key"


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
async def test_add_private_data_duplicate_key():
    """Test adding private data with duplicate key"""
    # First addition
    request1 = PrivateDataRequest(**{
        "collection": "test_collection",
        "key": "duplicate_key",
        "value": {"field": "value1"},
        "event_metadata": {
            "entity_id": "ENTITY-001",
            "event": "contract_negotiation",
            "timestamp": 1717987200.0
        }
    })
    
    response1 = await add_private_data(request1)
    assert response1.success is True
    
    # Second addition with same key (should overwrite or handle according to implementation)
    request2 = PrivateDataRequest(**{
        "collection": "test_collection",
        "key": "duplicate_key",
        "value": {"field": "value2"},
        "event_metadata": {
            "entity_id": "ENTITY-002",
            "event": "contract_updated",
            "timestamp": 1717987300.0
        }
    })
    
    response2 = await add_private_data(request2)
    assert response2.success is True
    assert response2.key == "duplicate_key"


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
async def test_add_private_data_large_payload():
    """Test adding private data with large payload"""
    large_value = {f"field_{i}": f"value_{i}" for i in range(10000)}
    
    request = PrivateDataRequest(
        collection="test_collection",
        key="large_data_key",
        value=large_value,
        event_metadata={
            "entity_id": "ENTITY-001",
            "event": "contract_negotiation",
            "timestamp": 1717987200.0
        }
    )
    
    response = await add_private_data(request)
    assert response.success is True
    assert response.key == "large_data_key"


# Performance tests
@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
async def test_add_private_data_response_time():
    """Test response time for adding private data"""
    request_data = {
        "collection": "test_collection",
        "key": "perf_test_key",
        "value": {"field": "value"},
        "event_metadata": {
            "entity_id": "ENTITY-001",
            "event": "performance_test",
            "timestamp": 1717987200.0
        }
    }
    
    start_time = time.time()
    request = PrivateDataRequest(**request_data)
    response = await add_private_data(request)
    end_time = time.time()
    
    response_time = end_time - start_time
    assert response_time < 1.0  # Should respond within 1 second
    assert response.success is True


@pytest.mark.asyncio
@patch('hierarchical_blockchain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierarchical_blockchain.api.v2.endpoints._private_collections', {"test_collection": {}})
async def test_add_private_data_concurrent_requests():
    """Test concurrent requests for adding private data"""
    async def make_request(key_suffix):
        request_data = {
            "collection": "test_collection",
            "key": f"concurrent_test_key_{key_suffix}",
            "value": {"field": f"value_{key_suffix}"},
            "event_metadata": {
                "entity_id": f"ENTITY-{key_suffix:03d}",
                "event": "concurrent_test",
                "timestamp": 1717987200.0 + key_suffix
            }
        }
        request = PrivateDataRequest(**request_data)
        return await add_private_data(request)
    
    # Create multiple concurrent requests
    tasks = [make_request(i) for i in range(10)]
    responses = await asyncio.gather(*tasks)
    
    # Check that all requests succeeded
    assert len(responses) == 10
    for response in responses:
        assert response.success is True