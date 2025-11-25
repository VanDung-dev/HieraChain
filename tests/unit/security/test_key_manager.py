"""
Unit tests for KeyManager module

This module contains unit tests for the KeyManager class functionality,
including key validation, revocation checks, permissions, and key creation.
"""

import time
from unittest.mock import Mock

from hierachain.security.key_manager import KeyManager, initialize_default_keys


def test_key_manager_initialization():
    """Test KeyManager initialization"""

    def init_key_manager():
        return KeyManager()

    km = init_key_manager()

    assert km is not None
    assert isinstance(km.storage, dict)
    assert isinstance(km.revoked_keys, set)
    assert isinstance(km.key_cache, dict)
    assert km.cache_ttl == 300


def test_is_valid_with_valid_key():
    """Test is_valid method with a valid key"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    mock_storage.get.return_value = '{"user_id": "test_user", "permissions": ["events"], "created_at": 1000, "expires_at": 9999999999}'
    km = KeyManager(storage_backend=mock_storage)
    valid_key = "valid_key_123456789012345"

    result = km.is_valid(valid_key)
    assert result is True
    # Because benchmark runs the function many times, we can't assert specific call count
    # But we can check if it was called at least once with the expected argument
    mock_storage.get.assert_any_call(f"api_key:{valid_key}")


def test_is_valid_with_invalid_key():
    """Test is_valid method with an invalid key"""
    km = KeyManager()

    def test_multiple_invalid_keys():
        results = []
        # Test with empty string key
        results.append(km.is_valid(""))
        # Test with short key
        results.append(km.is_valid("short"))
        # Test with non-existent key
        results.append(km.is_valid("non_existent_key"))
        return results

    results = test_multiple_invalid_keys()
    assert all(result is False for result in results)


def test_is_valid_with_expired_key():
    """Test is_valid method with an expired key"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    mock_storage.get.return_value = '{"user_id": "test_user", "permissions": ["events"], "created_at": 1000, "expires_at": 1001}'
    km = KeyManager(storage_backend=mock_storage)
    expired_key = "expired_key_123456789012345"

    result = km.is_valid(expired_key)
    assert result is False


def test_is_revoked_with_revoked_key():
    """Test is_revoked method with a revoked key"""
    km = KeyManager()
    revoked_key = "revoked_key_123456789012345"
    km.revoked_keys.add(revoked_key)

    result = km.is_revoked(revoked_key)
    assert result is True


def test_is_revoked_with_non_revoked_key():
    """Test is_revoked method with a non-revoked key"""
    km = KeyManager()
    non_revoked_key = "non_revoked_key_123456789012345"

    result = km.is_revoked(non_revoked_key)
    assert result is False


def test_has_permission_with_valid_permission():
    """Test has_permission method with valid permission"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    mock_storage.get.return_value = '{"user_id": "test_user", "permissions": ["events", "chains"], "created_at": 1000}'
    km = KeyManager(storage_backend=mock_storage)
    test_key = "test_key_123456789012345"

    def test_multiple_permissions():
        return [
            km.has_permission(test_key, 'events'),
            km.has_permission(test_key, 'chains')
        ]

    results = test_multiple_permissions()
    assert all(results)


def test_has_permission_with_wildcard_permission():
    """Test has_permission method with wildcard 'all' permission"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    mock_storage.get.return_value = '{"user_id": "admin_user", "permissions": ["all"], "created_at": 1000}'
    km = KeyManager(storage_backend=mock_storage)
    test_key = "admin_key_123456789012345"

    def test_multiple_permissions():
        return [
            km.has_permission(test_key, 'events'),
            km.has_permission(test_key, 'chains'),
            km.has_permission(test_key, 'any_resource')
        ]

    results = test_multiple_permissions()
    assert all(results)


def test_has_permission_without_permission():
    """Test has_permission method without required permission"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    mock_storage.get.return_value = '{"user_id": "limited_user", "permissions": ["events"], "created_at": 1000}'
    km = KeyManager(storage_backend=mock_storage)
    test_key = "limited_key_123456789012345"

    result = km.has_permission(test_key, 'chains')
    assert result is False


def test_get_user_with_valid_key():
    """Test get_user method with a valid key"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    mock_storage.get.return_value = '{"user_id": "specific_user", "permissions": ["events"], "created_at": 1000}'
    km = KeyManager(storage_backend=mock_storage)
    test_key = "user_key_123456789012345"

    result = km.get_user(test_key)
    assert result == 'specific_user'


def test_get_user_with_invalid_key():
    """Test get_user method with an invalid key"""
    km = KeyManager()
    invalid_key = "invalid_key_123456789012345"

    result = km.get_user(invalid_key)
    assert result is None


def test_get_app_details_with_valid_key():
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

    result = km.get_app_details(test_key)
    assert result == app_details


def test_get_app_details_with_invalid_key():
    """Test get_app_details method with an invalid key"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    mock_storage.get.return_value = None
    km = KeyManager(storage_backend=mock_storage)
    invalid_key = "invalid_key_123456789012345"

    result = km.get_app_details(invalid_key)
    assert result is None


def test_cache_key():
    """Test cache_key method"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    _key_data = {
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


def test_create_key():
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


def test_revoke_key():
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


def test_initialize_default_keys():
    """Test initialize_default_keys function"""
    result = initialize_default_keys()

    assert "demo_key" in result
    assert "admin_key" in result
    assert "key_manager" in result
    assert isinstance(result["key_manager"], KeyManager)
    assert len(result["demo_key"]) > 16
    assert len(result["admin_key"]) > 16


def test_is_valid_with_edge_cases():
    """Test is_valid method with edge cases"""
    km = KeyManager()

    def test_multiple_edge_cases():
        results = []
        # Test with None key
        results.append(km.is_valid(None))
        # Test with empty string
        results.append(km.is_valid(""))
        # Test with very short key
        results.append(km.is_valid("abc"))
        return results

    results = test_multiple_edge_cases()
    assert all(result is False for result in results[:3])

    # Test with very long key (should be valid if properly formatted)
    long_key = "hbc_" + "a" * 100
    # Add the key to storage first
    km.storage[long_key] = {
        'user_id': 'test_user',
        'permissions': ['events'],
        'created_at': time.time()
    }
    assert km.is_valid(long_key) is True


def test_has_permission_with_special_characters():
    """Test has_permission with special characters in resource names"""
    # Mock storage backend
    mock_storage = Mock()
    mock_storage.get.return_value = '{"user_id": "test_user", "permissions": ["event.read", "data/write", "sys_admin"], "created_at": 1000}'
    km = KeyManager(storage_backend=mock_storage)
    test_key = "special_chars_key_123456789012345"

    def test_multiple_permissions():
        return [
            km.has_permission(test_key, 'event.read'),
            km.has_permission(test_key, 'data/write'),
            km.has_permission(test_key, 'sys_admin'),
            km.has_permission(test_key, 'nonexistent_perm')
        ]

    results = test_multiple_permissions()

    assert all(results[:3])  # First three should be True
    assert not results[3]  # Last one should be False


def test_create_key_with_various_inputs():
    """Test create_key with various inputs including edge cases"""
    km = KeyManager()

    def create_multiple_keys():
        keys = []
        # Normal case
        keys.append(km.create_key("normal_user", ["read", "write"]))
        # User ID with special characters
        keys.append(km.create_key("user@domain.com", ["read"]))
        # Empty permissions
        keys.append(km.create_key("user_no_perms", []))
        return keys

    keys = create_multiple_keys()

    for key in keys:
        assert key.startswith("hbc_")
        assert len(key) > 16


def test_revoke_key_nonexistent():
    """Test revoke_key with nonexistent key"""
    km = KeyManager()
    # Should not throw exception
    km.revoke_key("nonexistent_key")
    assert km.is_revoked("nonexistent_key") is True


def test_key_creation_performance(benchmark):
    """Test performance of key creation operations"""
    km = KeyManager()
    def test_multiple_keys():
        start_time = time.perf_counter()

        # Create 100keys to test performance
        keys = []
        for i in range(100):
            key = km.create_key(f"user_{i}", ["read", "write"], {"name": f"App {i}"})
            keys.append(key)

        end_time = time.perf_counter()

        # Creating100 keys should take less than 2 seconds
        assert (end_time - start_time) < 2.0
        assert len(keys) == 100

    benchmark(test_multiple_keys)


def test_key_validation_performance(benchmark):
    """Test performance of key validation operations"""
    km = KeyManager()

    def create_keys():
        # Create testkeys
        keys = []
        for i in range(100):
            key = km.create_key(f"user_{i}", ["read", "write"], {"name": f"App {i}"})
            keys.append(key)

        start_time = time.perf_counter()

        #Validate 100 keys
        for key in keys:
            assert km.is_valid(key) is True

        end_time = time.perf_counter()

        # Validating 100 keys should take less than 1 second
        assert (end_time - start_time) < 1.0

    benchmark(create_keys)


def test_permission_check_performance(benchmark):
    """Test performance of permission checking operations"""
    # Mock storage backend with get method (like Redis)
    mock_storage = Mock()
    mock_storage.get.return_value = '{"user_id": "perf_test_user", "permissions": ["events", "chains", "admin_panel"], "created_at": 1000}'
    km = KeyManager(storage_backend=mock_storage)
    test_key = "perf_test_key_123456789012345"
    
    def test_multiple_permissions():
        start_time =time.perf_counter()

        # Check permissions 1000 times
        for _ in range(1000):
            assert km.has_permission(test_key, 'events') is True
            assert km.has_permission(test_key, 'chains') is True
            assert km.has_permission(test_key, 'admin_panel') is True

        end_time = time.perf_counter()

        # Checking permissions 1000 times should take less than 1 second
        assert (end_time - start_time) < 1.0

    benchmark(test_multiple_permissions)


def test_security_injection_attacks():
    """Test resistance to injection attacks"""
    km = KeyManager()
    
    # Test SQL injection attempts in user_id
    sql_injection_attempts = [
        "'; DROP TABLE users; --",
        "1'; WAITFOR DELAY '00:00:05'--",
        "admin'--",
        "' OR '1'='1",
        "\"; alert('XSS'); //",
        "<script>alert('XSS')</script>"
    ]

    def create_keys_with_injection_attempts():
        keys = []
        for attempt in sql_injection_attempts:
            # These should be treated as regular user_ids, not cause errors
            key = km.create_key(attempt, ["read"], {"name": "Injection Test"})
            keys.append(key)
        return keys

    keys = create_keys_with_injection_attempts()

    for key in keys:
        assert key is not None
        assert km.is_valid(key) is True
        # Keys should not have special interpretation of these characters
        assert "'" not in key or "\"" not in key  # Our key generation should not include these


def test_security_xss_attacks():
    """Testresistance to XSS attacks in app details"""
    km = KeyManager()
    
    # Test XSS attempts in app details
    xss_attempts = [
        {"name": "<script>alert('XSS')</script>", "version": "1.0"},
        {"name": "Test App", "description": "javascript:alert('XSS')"},
        {"name": "Test App", "callback": "javascript:eval('alert(1)')"},
        {"name": "Test<img src=x onerror=alert(1)>App", "version": "1.0"}
    ]

    def test_xss_attempts():
        results = []
        for i, attempt in enumerate(xss_attempts):
            # These should be treated as regular app details, not cause errors
            key = km.create_key(f"xss_test_user_{i}", ["read"], attempt)
            assert key is not None
            results.append((key, km.is_valid(key)))
        return results

    results = test_xss_attempts()

    # When we retrieve app details, they should be preserved as-is
    for key, is_valid in results:
        assert is_valid is True
        details = km.get_app_details(key)
        assert details is not None


def test_security_directory_traversal():
    """Test resistance to directory traversal attacks"""
    km = KeyManager()
    
    # Test directory traversal attempts in user_id
    traversal_attempts = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\cmd.exe",
        "/etc/passwd",
        "../../config/database.yml",
        "..\\\\..\\\\..\\\\boot.ini"
    ]

    def test_traversal_attempts():
        results = []
        for attempt in traversal_attempts:
            # These should be treated as regular user_ids, not cause filesystem access
            key = km.create_key(attempt, ["read"], {"name": "Traversal Test"})
            assert key is not None
            results.append((key, km.is_valid(key)))
        return results

    results = test_traversal_attempts()

    for key, is_valid in results:
        assert is_valid is True
