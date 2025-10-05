"""
Unit tests for API v3 package __init__.py

This module contains unit tests for the API v3 package exports,
ensuring all expected classes and functions are properly exported.
"""

from api.v3 import VerifyAPIKey, ResourcePermissionChecker, create_verify_api_key


def test_verify_api_key_export():
    """Test that VerifyAPIKey is properly exported from the package"""
    assert VerifyAPIKey is not None
    # Check that it's the right type (class)
    assert isinstance(VerifyAPIKey, type)


def test_resource_permission_checker_export():
    """Test that ResourcePermissionChecker is properly exported from the package"""
    assert ResourcePermissionChecker is not None
    # Check that it's the right type (class)
    assert isinstance(ResourcePermissionChecker, type)


def test_create_verify_api_key_export():
    """Test that create_verify_api_key function is properly exported from the package"""
    assert create_verify_api_key is not None
    # Check that it's callable
    assert callable(create_verify_api_key)


def test_all_exports():
    """Test that __all__ contains all expected exports"""
    from api.v3 import __all__
    
    expected_exports = [
        'VerifyAPIKey',
        'ResourcePermissionChecker', 
        'create_verify_api_key'
    ]
    
    assert __all__ == expected_exports
    
    # Check that each export is actually available
    for export in expected_exports:
        assert export in __all__
        # Try to get the attribute to make sure it exists
        assert getattr(__import__('api.v3', fromlist=[export]), export) is not None