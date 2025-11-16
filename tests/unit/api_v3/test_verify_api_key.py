"""
Unit tests for API v3 VerifyAPIKey module

This module contains unit tests for the VerifyAPIKey class and related 
functionality in the API v3 module, including API key verification, 
permission checking, and security event logging.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from hierarchical_blockchain.api.v3.verify import VerifyAPIKey, ResourcePermissionChecker, create_verify_api_key


@pytest.fixture
def mock_key_manager():
    """Mock KeyManager for testing"""
    with patch('hierarchical_blockchain.api.v3.verify.KeyManager') as mock_km:
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
async def test_verify_api_key_success(mock_key_manager, default_config):
    """Test successful API key verification"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    context = await verify_key("valid_api_key")
    
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
async def test_verify_api_key_cache_enabled(mock_key_manager, default_config):
    """Test that caching is used when enabled"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    await verify_key("valid_api_key")
    
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


def test_check_resource_permission(mock_key_manager, default_config):
    """Test resource permission checking"""
    verify_key = VerifyAPIKey(default_config)
    verify_key.key_manager = mock_key_manager
    
    result = verify_key.check_resource_permission("test_api_key", "test_resource")
    
    assert result is True
    mock_key_manager.has_permission.assert_called_once_with("test_api_key", "test_resource")


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


@pytest.mark.asyncio
async def test_log_security_event(mock_key_manager, default_config):
    """Test that security events are logged"""
    with patch('hierarchical_blockchain.api.v3.verify.logger') as mock_logger:
        verify_key = VerifyAPIKey(default_config)
        verify_key.key_manager = mock_key_manager
        
        # Call the method that logs security events
        _context = await verify_key("valid_api_key")
        
        # Check if logger was called
        assert mock_logger.info.called