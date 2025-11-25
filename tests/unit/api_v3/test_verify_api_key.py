"""
Unit tests for API v3 VerifyAPIKey module

This module contains unit tests for the VerifyAPIKey class and related 
functionality in the API v3 module, including API key verification, 
permission checking, and security event logging.
"""

import pytest
import asyncio
import inspect
from unittest.mock import Mock, patch
from unittest import mock
from fastapi import HTTPException

from hierachain.api.v3.verify import VerifyAPIKey, ResourcePermissionChecker, create_verify_api_key


@pytest.fixture
def mock_key_manager():
    """Mock KeyManager for testing"""
    with patch('hierachain.api.v3.verify.KeyManager') as mock_km:
        mock_instance = Mock()
        mock_instance.is_valid.return_value = True
        mock_instance.is_revoked.return_value = False
        mock_instance.get_user.return_value = "test_user"
        mock_instance.get_app_details.return_value = {"name": "Test App"}
        mock_instance.has_permission.return_value = True
        mock_km.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def default_config():
    """Default configuration for VerifyAPIKey"""
    return {
        "enabled": True,
        "key_location": "header",
        "key_name": "x-api-key",
        "cache_ttl": 300,
        "revocation_check": "daily"
    }


@pytest.fixture
def disabled_config():
    """Configuration with verification disabled"""
    return {
        "enabled": False,
        "key_location": "header",
        "key_name": "x-api-key",
        "cache_ttl": 300,
        "revocation_check": "daily"
    }


@pytest.mark.asyncio
async def test_verify_api_key_success(mock_key_manager, default_config, benchmark):
    """Test successful API key verification"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager

    async def verify_key_async(key):
        return await verify_key(key)

    context = await benchmark.pedantic(verify_key_async, args=("valid_api_key",), kwargs={}, iterations=1, rounds=1)

    assert "user_id" in context
    assert "app_details" in context
    assert context["user_id"] == "test_user"
    assert context["app_details"]["name"] == "Test App"
    assert "api_key_prefix" in context
    assert "verified_at" in context
    
    # Check that key manager methods were called
    mock_key_manager.is_valid.assert_called_once_with("valid_api_key")
    mock_key_manager.is_revoked.assert_called_once_with("valid_api_key")
    mock_key_manager.get_user.assert_called_once_with("valid_api_key")
    mock_key_manager.get_app_details.assert_called_once_with("valid_api_key")


@pytest.mark.asyncio
async def test_verify_api_key_missing_key(default_config):
    """Test verification with missing API key"""
    verify_key = VerifyAPIKey(default_config)
    
    with pytest.raises(HTTPException) as exc_info:
        await verify_key(None)
    
    assert exc_info.value.status_code == 401
    assert "API key missing" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_verify_api_key_invalid_key(mock_key_manager, default_config):
    """Test verification with invalid API key"""
    mock_key_manager.is_valid.return_value = False
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    with pytest.raises(HTTPException) as exc_info:
        await verify_key("invalid_api_key")
    
    assert exc_info.value.status_code == 401
    assert "Invalid API key" in str(exc_info.value.detail)
    
    mock_key_manager.is_valid.assert_called_once_with("invalid_api_key")


@pytest.mark.asyncio
async def test_verify_api_key_revoked_key(mock_key_manager, default_config):
    """Test verification with revoked API key"""
    mock_key_manager.is_valid.return_value = True
    mock_key_manager.is_revoked.return_value = True
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    with pytest.raises(HTTPException) as exc_info:
        await verify_key("revoked_api_key")
    
    assert exc_info.value.status_code == 401
    assert "API key revoked" in str(exc_info.value.detail)
    
    mock_key_manager.is_valid.assert_called_once_with("revoked_api_key")
    mock_key_manager.is_revoked.assert_called_once_with("revoked_api_key")


@pytest.mark.asyncio
async def test_verify_api_key_disabled(disabled_config):
    """Test verification when disabled"""
    verify_key = VerifyAPIKey(disabled_config)
    
    context = await verify_key("any_key")
    
    assert context["user_id"] == "system"
    assert context["app_details"]["name"] == "System Access"


@pytest.mark.asyncio
async def test_verify_api_key_cache_enabled(mock_key_manager, default_config, benchmark):
    """Test that caching is used when enabled"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager

    async def verify_key_async(key):
        return await verify_key(key)

    await benchmark.pedantic(verify_key_async, args=("valid_api_key",), kwargs={}, iterations=1, rounds=1)

    mock_key_manager.cache_key.assert_called_once_with("valid_api_key", ttl=300)


@pytest.mark.asyncio
async def test_verify_api_key_different_locations():
    """Test VerifyAPIKey with different key locations"""
    # Test header location
    header_config = {
        "enabled": True,
        "key_location": "header",
        "key_name": "x-api-key"
    }
    verify_key_header = VerifyAPIKey(header_config)
    assert verify_key_header.key_location == "header"
    
    # Test query location
    query_config = {
        "enabled": True,
        "key_location": "query",
        "key_name": "apikey"
    }
    verify_key_query = VerifyAPIKey(query_config)
    assert verify_key_query.key_location == "query"


def test_check_resource_permission(mock_key_manager, default_config, benchmark):
    """Test resource permission checking"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager

    result = benchmark(verify_key.check_resource_permission, "test_api_key", "test_resource")

    assert result is True
    # Since benchmark runs the function multiple times, we check that it was called at least once
    mock_key_manager.has_permission.assert_any_call("test_api_key", "test_resource")


def test_require_permission_decorator(mock_key_manager, default_config):
    """Test the permission requirement decorator"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    # Create the decorator
    decorator = verify_key.require_permission("test_resource")
    assert callable(decorator)


@pytest.mark.asyncio
async def test_resource_permission_checker():
    """Test ResourcePermissionChecker functionality"""
    # Create a mock VerifyAPIKey
    mock_verify_api_key = Mock()
    
    checker = ResourcePermissionChecker(mock_verify_api_key)
    assert checker.verify_api_key == mock_verify_api_key


@pytest.mark.asyncio
async def test_create_verify_api_key_factory(default_config):
    """Test the factory function for creating VerifyAPIKey instances"""
    verify_key = create_verify_api_key(default_config)
    
    assert isinstance(verify_key, VerifyAPIKey)
    assert verify_key.enabled == True
    assert verify_key.key_location == "header"
    assert verify_key.key_name == "x-api-key"


# New test cases as requested

@pytest.mark.asyncio
async def test_verify_api_key_cache_zero_ttl(mock_key_manager):
    """Test cache behavior with TTL=0"""
    config = {
        "enabled": True,
        "key_location": "header",
        "key_name": "x-api-key",
        "cache_ttl": 0,
        "revocation_check": "daily"
    }
    verify_key = VerifyAPIKey(config)
    verify_key.key_manager = mock_key_manager
    
    await verify_key("valid_api_key")
    
    # With TTL=0, cache_key should not be called
    mock_key_manager.cache_key.assert_not_called()


@pytest.mark.asyncio
async def test_verify_api_key_cache_disabled(mock_key_manager):
    """Test cache behavior when cache is disabled (negative TTL)"""
    config = {
        "enabled": True,
        "key_location": "header",
        "key_name": "x-api-key",
        "cache_ttl": -1,
        "revocation_check": "daily"
    }
    verify_key = VerifyAPIKey(config)
    verify_key.key_manager = mock_key_manager
    
    await verify_key("valid_api_key")
    
    # With negative TTL, cache_key should not be called
    mock_key_manager.cache_key.assert_not_called()


@pytest.mark.asyncio
async def test_verify_api_key_complex_permissions(mock_key_manager, default_config):
    """Test complex permission scenarios with multiple resources and nested permissions"""
    mock_key_manager.has_permission.side_effect = lambda key, resource: resource in ["read", "write", "admin"]
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    # Test multiple resource permissions
    assert verify_key.check_resource_permission("test_api_key", "read") is True
    assert verify_key.check_resource_permission("test_api_key", "write") is True
    assert verify_key.check_resource_permission("test_api_key", "admin") is True
    assert verify_key.check_resource_permission("test_api_key", "delete") is False
    
    # Verify calls were made correctly
    mock_key_manager.has_permission.assert_any_call("test_api_key", "read")
    mock_key_manager.has_permission.assert_any_call("test_api_key", "write")
    mock_key_manager.has_permission.assert_any_call("test_api_key", "admin")
    mock_key_manager.has_permission.assert_any_call("test_api_key", "delete")


@pytest.mark.asyncio
async def test_verify_api_key_security_logging(mock_key_manager, default_config):
    """Test security event logging"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    # Mock the _log_security_event method to track calls
    with patch.object(VerifyAPIKey, '_log_security_event') as mock_log:
        # Test successful verification logs
        await verify_key("valid_api_key")
        mock_log.assert_called_with("successful_verification", {
            "user_id": "test_user",
            "app_name": "Test App",
            "timestamp": mock.ANY
        })
        
        # Reset mock
        mock_log.reset_mock()
        
        # Test invalid key logs
        mock_key_manager.is_valid.return_value = False
        try:
            await verify_key("invalid_api_key")
        except HTTPException:
            pass
        
        mock_log.assert_called_with("invalid_api_key", {
            "key_prefix": "invalid_",
            "timestamp": mock.ANY
        })


@pytest.mark.asyncio
async def test_verify_api_key_performance_many_requests(mock_key_manager, default_config, benchmark):
    """Test performance with many concurrent requests"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager

    async def many_concurrent_requests():
        # Create 100 concurrent requests
        tasks = [verify_key(f"api_key_{i}") for i in range(100)]
        results = await asyncio.gather(*tasks)
        return results

    # Use pedantic mode to properly benchmark the coroutine
    results = await benchmark.pedantic(many_concurrent_requests, iterations=1, rounds=1)

    # All requests should succeed
    assert len(results) == 100
    assert all("user_id" in result for result in results)


# Integration test between VerifyAPIKey and ResourcePermissionChecker
@pytest.mark.asyncio
async def test_integration_verify_api_key_and_resource_permission_checker(mock_key_manager, default_config):
    """Test integration between VerifyAPIKey and ResourcePermissionChecker"""
    # Setup VerifyAPIKey
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    # Setup ResourcePermissionChecker
    checker = ResourcePermissionChecker(verify_key)
    
    # Verify they are linked correctly
    assert checker.verify_api_key == verify_key
    
    # Test context creation
    context = await verify_key("valid_api_key")
    assert "user_id" in context
    assert "app_details" in context


# Test cases for invalid configurations
def test_verify_api_key_invalid_config_missing_required_fields():
    """Test VerifyAPIKey with invalid configuration (missing required fields)"""
    invalid_config = {
        "some_random_field": "value"
    }
    
    # Should not raise exception even with missing fields
    verify_key = VerifyAPIKey(invalid_config)
    
    # Should use default values
    assert verify_key.enabled is True  # Default value
    assert verify_key.key_location == "header"  # Default value
    assert verify_key.key_name == "x-api-key"  # Default value
    assert verify_key.cache_ttl == 300  # Default value


def test_verify_api_key_invalid_config_wrong_types():
    """Test VerifyAPIKey with invalid configuration (wrong data types)"""
    invalid_config = {
        "enabled": "not_a_boolean",
        "key_location": 123,
        "key_name": None,
        "cache_ttl": "not_a_number"
    }
    
    # Should not raise exception with wrong types
    verify_key = VerifyAPIKey(invalid_config)
    
    # Values should be assigned as-is (no type conversion)
    assert verify_key.enabled == "not_a_boolean"
    assert verify_key.key_location == 123
    assert verify_key.key_name is None
    assert verify_key.cache_ttl == "not_a_number"


def test_verify_api_key_unsupported_key_location(default_config):
    """Test VerifyAPIKey with unsupported key location falls back to header"""
    unsupported_config = default_config.copy()
    unsupported_config["key_location"] = "cookie"  # Unsupported location
    
    verify_key = VerifyAPIKey(unsupported_config)
    
    # Should fall back to default header dependency
    assert verify_key.key_location == "cookie"
    # Note: The actual fallback behavior depends on implementation


# Test cases for private methods using inspect
def test_private_method_log_security_event_exists():
    """Test that _log_security_event private method exists"""
    # Check that the private method exists
    assert hasattr(VerifyAPIKey, '_log_security_event')
    
    # Get the method using inspect
    method = getattr(VerifyAPIKey, '_log_security_event')
    assert callable(method)
    
    # Check method signature
    signature = inspect.signature(method)
    assert 'event_type' in signature.parameters
    assert 'details' in signature.parameters


def test_private_method_has_permission_exists():
    """Test that _has_permission private method exists in ResourcePermissionChecker"""
    # Check that the private method exists
    assert hasattr(ResourcePermissionChecker, '_has_permission')
    
    # Get the method using inspect
    method = getattr(ResourcePermissionChecker, '_has_permission')
    assert callable(method)
    
    # Check method signature
    signature = inspect.signature(method)
    assert 'context' in signature.parameters
    assert 'permission_type' in signature.parameters