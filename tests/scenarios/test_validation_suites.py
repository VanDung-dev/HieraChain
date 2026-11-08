"""Behavioral validation of API keys."""

import pytest

from hierachain.security import KeyManager


@pytest.mark.low
def test_api_key_verification():
    """
    Test API key verification system with different key locations.
    Validates API security implementation.
    """
    # Test KeyManager functionality
    key_manager = KeyManager()
    
    # Create test API key
    test_key = key_manager.create_key(
        user_id="test_user",
        permissions=["events", "chains"],
        app_details={"name": "Test App"}
    )
    
    # Test key validation
    assert key_manager.is_valid(test_key) is True
    assert key_manager.is_revoked(test_key) is False
    assert key_manager.has_permission(test_key, "events") is True
    assert key_manager.has_permission(test_key, "admin") is False
    
    # Test key revocation
    key_manager.revoke_key(test_key)
    assert key_manager.is_revoked(test_key) is True
