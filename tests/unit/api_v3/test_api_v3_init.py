"""
Unit tests for API v3 package __init__.py

This module contains unit tests for the API v3 package exports,
ensuring all expected classes and functions are properly exported.
"""

import pytest
import inspect
from hierarchical_blockchain import api
from hierarchical_blockchain.api.v3 import verify


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


def test_import_exception_handling(monkeypatch):
    """Test exception handling when imports fail"""
    # Mock the verify module to raise ImportError
    with pytest.raises(ImportError):
        monkeypatch.setattr('sys.modules', {
            'hierarchical_blockchain.api.v3.verify': None
        })
        # Re-import the module to trigger the import error
        from importlib import reload
        import hierarchical_blockchain.api.v3
        reload(hierarchical_blockchain.api.v3)


def test_function_signatures():
    """Test signatures of exported functions"""
    import inspect
    
    # Check VerifyAPIKey class signature
    verify_api_key_signature = inspect.signature(api.v3.VerifyAPIKey.__init__)
    assert 'config' in verify_api_key_signature.parameters
    
    # Check ResourcePermissionChecker class signature
    resource_checker_signature = inspect.signature(api.v3.ResourcePermissionChecker.__init__)
    assert 'verify_api_key' in resource_checker_signature.parameters
    
    # Check create_verify_api_key function signature
    create_func_signature = inspect.signature(api.v3.create_verify_api_key)
    assert 'config' in create_func_signature.parameters


def test_private_methods_exist_using_inspect():
    """Test that private methods exist using inspect module"""
    # Check VerifyAPIKey private methods
    verify_api_key_members = inspect.getmembers(verify.VerifyAPIKey, predicate=inspect.isfunction)
    private_methods = [name for name, _ in verify_api_key_members if name.startswith('_') and not name.startswith('__')]
    assert '_log_security_event' in private_methods
    
    # Check ResourcePermissionChecker private methods
    resource_checker_members = inspect.getmembers(verify.ResourcePermissionChecker, predicate=inspect.isfunction)
    private_methods = [name for name, _ in resource_checker_members if name.startswith('_') and not name.startswith('__')]
    assert '_has_permission' in private_methods
    assert '_has_event_permission' in private_methods
    assert '_has_chain_permission' in private_methods
    assert '_has_proof_permission' in private_methods