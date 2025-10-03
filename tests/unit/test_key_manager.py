"""
Unit tests for KeyManager module

This module contains unit tests for the KeyManager class functionality,
including key validation, revocation checks, permissions, and key creation.
"""

import time
import pytest
from unittest.mock import Mock, patch
from security.key_manager import KeyManager, initialize_default_keys


class TestKeyManager:
    """Test suite for KeyManager class"""

    def test_key_manager_initialization(self):
        """Test KeyManager initialization"""
        km = KeyManager()
        assert km is not None
        assert isinstance(km.storage, dict)
        assert isinstance(km.revoked_keys, set)
        assert isinstance(km.key_cache, dict)
        assert km.cache_ttl == 300

    def test_is_valid_with_valid_key(self):
        """Test is_valid method with a valid key"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        mock_storage.get.return_value = '{"user_id": "test_user", "permissions": ["events"], "created_at": 1000, "expires_at": 9999999999}'
        km = KeyManager(storage_backend=mock_storage)
        valid_key = "valid_key_123456789012345"
        
        assert km.is_valid(valid_key) is True
        mock_storage.get.assert_called_once_with(f"api_key:{valid_key}")

    def test_is_valid_with_invalid_key(self):
        """Test is_valid method with an invalid key"""
        km = KeyManager()
        
        # Test with None key
        assert km.is_valid(None) is False
        
        # Test with short key
        assert km.is_valid("short") is False
        
        # Test with non-existent key
        assert km.is_valid("non_existent_key") is False

    def test_is_valid_with_expired_key(self):
        """Test is_valid method with an expired key"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        mock_storage.get.return_value = '{"user_id": "test_user", "permissions": ["events"], "created_at": 1000, "expires_at": 1001}'
        km = KeyManager(storage_backend=mock_storage)
        expired_key = "expired_key_123456789012345"
        
        assert km.is_valid(expired_key) is False

    def test_is_revoked_with_revoked_key(self):
        """Test is_revoked method with a revoked key"""
        km = KeyManager()
        revoked_key = "revoked_key_123456789012345"
        km.revoked_keys.add(revoked_key)
        
        assert km.is_revoked(revoked_key) is True

    def test_is_revoked_with_non_revoked_key(self):
        """Test is_revoked method with a non-revoked key"""
        km = KeyManager()
        non_revoked_key = "non_revoked_key_123456789012345"
        
        assert km.is_revoked(non_revoked_key) is False

    def test_has_permission_with_valid_permission(self):
        """Test has_permission method with valid permission"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        mock_storage.get.return_value = '{"user_id": "test_user", "permissions": ["events", "chains"], "created_at": 1000}'
        km = KeyManager(storage_backend=mock_storage)
        test_key = "test_key_123456789012345"
        
        assert km.has_permission(test_key, 'events') is True
        assert km.has_permission(test_key, 'chains') is True

    def test_has_permission_with_wildcard_permission(self):
        """Test has_permission method with wildcard 'all' permission"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        mock_storage.get.return_value = '{"user_id": "admin_user", "permissions": ["all"], "created_at": 1000}'
        km = KeyManager(storage_backend=mock_storage)
        test_key = "admin_key_123456789012345"
        
        assert km.has_permission(test_key, 'events') is True
        assert km.has_permission(test_key, 'chains') is True
        assert km.has_permission(test_key, 'any_resource') is True

    def test_has_permission_without_permission(self):
        """Test has_permission method without required permission"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        mock_storage.get.return_value = '{"user_id": "limited_user", "permissions": ["events"], "created_at": 1000}'
        km = KeyManager(storage_backend=mock_storage)
        test_key = "limited_key_123456789012345"
        
        assert km.has_permission(test_key, 'chains') is False

    def test_get_user_with_valid_key(self):
        """Test get_user method with a valid key"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        mock_storage.get.return_value = '{"user_id": "specific_user", "permissions": ["events"], "created_at": 1000}'
        km = KeyManager(storage_backend=mock_storage)
        test_key = "user_key_123456789012345"
        
        assert km.get_user(test_key) == 'specific_user'

    def test_get_user_with_invalid_key(self):
        """Test get_user method with an invalid key"""
        km = KeyManager()
        invalid_key = "invalid_key_123456789012345"
        
        assert km.get_user(invalid_key) is None

    def test_get_app_details_with_valid_key(self):
        """Test get_app_details method with a valid key"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        app_details = {
            'name': 'Test Application',
            'version': '1.0'
        }
        mock_storage.get.return_value = '{"user_id": "test_user", "permissions": ["events"], "app_details": {"name": "Test Application", "version": "1.0"}, "created_at": 1000}'
        km = KeyManager(storage_backend=mock_storage)
        test_key = "app_key_123456789012345"
        
        assert km.get_app_details(test_key) == app_details

    def test_get_app_details_with_invalid_key(self):
        """Test get_app_details method with an invalid key"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        mock_storage.get.return_value = None
        km = KeyManager(storage_backend=mock_storage)
        invalid_key = "invalid_key_123456789012345"
        
        assert km.get_app_details(invalid_key) is None

    def test_cache_key(self):
        """Test cache_key method"""
        # Mock storage backend with get method (like Redis)
        mock_storage = Mock()
        key_data = {
            'user_id': 'cached_user',
            'permissions': ['events'],
            'created_at': time.time()
        }
        mock_storage.get.return_value = '{"user_id": "cached_user", "permissions": ["events"], "created_at": 1000}'
        km = KeyManager(storage_backend=mock_storage)
        test_key = "cache_key_123456789012345"
    
        # Cache the key
        km.cache_key(test_key, ttl=60)
        
        # Check if it's in cache
        assert test_key in km.key_cache
        # Note: we can't directly compare the data since it's parsed from JSON
        assert km.key_cache[test_key]['ttl'] == 60

    def test_create_key(self):
        """Test create_key method"""
        km = KeyManager()
        user_id = "new_user"
        permissions = ["events", "chains"]
        app_details = {"name": "New App", "version": "1.0"}
        
        # Create a new key
        new_key = km.create_key(user_id, permissions, app_details)
        
        # Check that key was created
        assert new_key is not None
        assert new_key.startswith("hbc_")
        assert len(new_key) > 16
        
        # Check that key data is stored
        assert new_key in km.storage
        stored_data = km.storage[new_key]
        assert stored_data['user_id'] == user_id
        assert stored_data['permissions'] == permissions
        assert stored_data['app_details'] == app_details

    def test_revoke_key(self):
        """Test revoke_key method"""
        km = KeyManager()
        test_key = "revoke_key_123456789012345"
        
        # Add key to storage
        km.storage[test_key] = {
            'user_id': 'test_user',
            'permissions': ['events'],
            'created_at': time.time()
        }
        
        # Revoke the key
        km.revoke_key(test_key)
        
        # Check that key is revoked
        assert km.is_revoked(test_key) is True
        
        # Check that key is removed from cache if it was there
        km.key_cache = {test_key: {'data': {}, 'cached_at': time.time(), 'ttl': 300}}
        km.revoke_key(test_key)
        assert test_key not in km.key_cache

    def test_initialize_default_keys(self):
        """Test initialize_default_keys function"""
        result = initialize_default_keys()
        
        assert "demo_key" in result
        assert "admin_key" in result
        assert "key_manager" in result
        assert isinstance(result["key_manager"], KeyManager)
        assert len(result["demo_key"]) > 16
        assert len(result["admin_key"]) > 16


if __name__ == "__main__":
    pytest.main([__file__])