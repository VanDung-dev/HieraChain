"""
Unit tests for API v3 package __init__.py

This module contains unit tests for the API v3 package exports,
ensuring all expected classes and functions are properly exported.
"""

from hierarchical_blockchain import api


def test_verify_api_key_export():
    """Test that VerifyAPIKey is properly exported from the package"""
    assert api.v3.VerifyAPIKey is not None
    # Check that it's the right type (class)
    assert isinstance(api.v3.VerifyAPIKey, type)


def test_resource_permission_checker_export():
    """Test that ResourcePermissionChecker is properly exported from the package"""
    assert api.v3.ResourcePermissionChecker is not None
    # Check that it's the right type (class)
    assert isinstance(api.v3.ResourcePermissionChecker, type)


def test_create_verify_api_key_export():
    """Test that create_verify_api_key function is properly exported from the package"""
    assert api.v3.create_verify_api_key is not None
    # Check that it's callable
    assert callable(api.v3.create_verify_api_key)


def test_all_exports():
    """Test that __all__ contains all expected exports"""
    expected_exports = [
        'VerifyAPIKey',
        'ResourcePermissionChecker', 
        'create_verify_api_key'
    ]
    
    assert api.v3.__all__ == expected_exports
    
    # Check that each export is actually available
    for export in expected_exports:
        assert export in api.v3.__all__
        # Try to get the attribute to make sure it exists
        assert getattr(api.v3, export) is not None