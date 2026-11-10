"""Recovery checks for API key/cache lifecycle."""

import time

import pytest

from hierachain.adapters.database.auth_state import _key_digest
from hierachain.security import KeyManager


@pytest.mark.recovery
def test_api_key_revocation_recovery():
    """
    Test recovery from compromised API key scenarios.
    Validates key revocation and replacement workflow.
    """
    # Using a simple dict as storage backend for testing
    storage_backend = {}
    key_manager = KeyManager(storage_backend)
    
    # Create initial key
    original_key = key_manager.create_key(
        user_id="test_user",
        permissions=["events", "chains"],
        app_details={"name": "Test App"}
    )
    
    # Test initial key is created (not necessarily valid yet)
    assert isinstance(original_key, str)
    assert len(original_key) > 0
    
    # Test key storage - the key shouldalready be stored by create_key
    key_data = key_manager._get_key_data(original_key)
    assert key_data is not None # This was failing, let's check why
    
    # Test key revocation
    key_manager.revoke_key(original_key)
    assert key_manager.is_revoked(original_key) is True
    
    # Test replacement key creation
    replacement_key = key_manager.create_key(
        user_id="test_user",
        permissions=["events", "chains"],
        app_details={"name": "Test App -Replacement"}
    )
    
    # Replacement should be valid and different
    assert isinstance(replacement_key, str)
    assert len(replacement_key) > 0
    assert replacement_key != original_key

@pytest.mark.recovery
def test_api_cache_recovery():
    """
    Test API key cache recovery after cache failure.
    Validates cache rebuilding and performance recovery.
    """
    # Using a simple dict as storage backend for testing
    storage_backend = {}
    key_manager = KeyManager(storage_backend)
    
    # Create test key
    test_key = key_manager.create_key("cache_test_user", ["events"])
    
    # The key should already be stored by create_key, no need to manually add
    
    # Manually add to cache since cache_key depends on key existing in storage
    key_data = key_manager._get_key_data(test_key)
    #Fix: Check if key_data exists before trying to cache it
    if key_data is not None:
        key_manager.key_cache[_key_digest(test_key)] = {
            'data': key_data,
            'cached_at': time.time(),
            'ttl': 300
        }
    
    # Verify key is cached
    assert _key_digest(test_key) in key_manager.key_cache
    
    # Simulate cache failure/clear
    key_manager.key_cache.clear()
    assert _key_digest(test_key) not in key_manager.key_cache
    
    # Test cache rebuild on next access
    key_data = key_manager._get_key_data(test_key)
    assert key_data is not None  # Should retrieve from storage
    
    # Test re-caching
    key_manager.cache_key(test_key, ttl=300)
    assert _key_digest(test_key) in key_manager.key_cache
