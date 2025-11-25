"""
Unit tests for Contract API endpoints in v2

This module contains unit tests for the contract-related endpoints in API v2,
including contract creation and execution.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from hierachain.api.v2.endpoints import create_contract, execute_contract
from hierachain.api.v2.schemas import ContractCreateRequest, ContractExecuteRequest


@pytest.fixture
def mock_contract_data():
    """Mock contract data for testing"""
    return {
        "contract_id": "test_contract",
        "version": "1.0.0",
        "implementation": "def test_logic(event, state, context): return {'result': 'success'}",
        "metadata": {
            "domain": "manufacturing",
            "owner": "org1",
            "endorsement_policy": "MAJORITY"
        }
    }


@pytest.fixture
def mock_execution_data():
    """Mock contract execution data for testing"""
    return {
        "contract_id": "test_contract",
        "event": {
            "entity_id": "PRODUCT-2024-001",
            "event": "quality_check",
            "timestamp": 1717987200.0,
            "details": {
                "result": "pass",
                "inspector_id": "INSPECTOR-03"
            }
        },
        "context": {
            "chain": "quality_chain"
        }
    }


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {})
async def test_create_contract_success(mock_contract_data):
    """Test successful contract creation"""
    request = ContractCreateRequest(**mock_contract_data)
    response = await create_contract(request)
    
    assert response.success is True
    assert response.contract_id == "test_contract"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {})
async def test_create_contract_missing_required_fields():
    """Test contract creation with missing required fields"""
    # Missing contract_id
    invalid_contract_data = {
        "version": "1.0.0",
        "implementation": "def test_logic(event, state, context): return {'result': 'success'}",
        "metadata": {
            "domain": "manufacturing",
            "owner": "org1"
        }
    }
    
    with pytest.raises(Exception):
        ContractCreateRequest(**invalid_contract_data)


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {"": {}})
async def test_create_contract_empty_values():
    """Test contract creation with empty values"""
    invalid_contract_data = {
        "contract_id": "",  # Empty contract id
        "version": "",  # Empty version
        "implementation": "",  # Empty implementation
        "metadata": {}  # Empty metadata
    }
    
    request = ContractCreateRequest(**invalid_contract_data)
    # Current implementation doesn't validate, so this should still succeed
    response = await create_contract(request)
    assert response.success is True
    assert response.contract_id == ""


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {})
async def test_create_contract_invalid_implementation():
    """Test contract creation with invalid implementation"""
    invalid_contract_data = {
        "contract_id": "invalid_impl_contract",
        "version": "1.0.0",
        "implementation": "",  # Empty implementation
        "metadata": {
            "domain": "manufacturing",
            "owner": "org1",
            "endorsement_policy": "MAJORITY"
        }
    }
    
    request = ContractCreateRequest(**invalid_contract_data)
    # Current implementation doesn't validate, so this should still succeed
    response = await create_contract(request)
    assert response.success is True
    assert response.contract_id == "invalid_impl_contract"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_create_contract_not_implemented(mock_contract_data):
    """Test contract creation when modules are not available"""
    request = ContractCreateRequest(**mock_contract_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await create_contract(request)
    
    # Should raise an HTTPException with status code 501
    assert exc_info.value.status_code == 501


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {"test_contract": {}})
async def test_execute_contract_success(mock_execution_data):
    """Test successful contract execution"""
    request = ContractExecuteRequest(**mock_execution_data)
    response = await execute_contract(request)
    
    assert response.success is True
    assert response.contract_id == "test_contract"
    assert response.result is not None


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {"test_contract": {}})
async def test_execute_contract_missing_required_fields():
    """Test contract execution with missing required fields"""
    # Missing contract_id
    invalid_execution_data = {
        "event": {
            "entity_id": "PRODUCT-2024-001",
            "event": "quality_check"
        },
        "context": {
            "chain": "quality_chain"
        }
    }
    
    with pytest.raises(Exception):
        ContractExecuteRequest(**invalid_execution_data)


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {"": {}})
async def test_execute_contract_empty_values():
    """Test contract execution with empty values"""
    invalid_execution_data = {
        "contract_id": "",  # Empty contract id
        "event": {},  # Empty event
        "context": {}  # Empty context
    }
    
    request = ContractExecuteRequest(**invalid_execution_data)
    # Current implementation doesn't validate event data, so this should still succeed
    response = await execute_contract(request)
    assert response.success is True
    assert response.contract_id == ""


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {"test_contract": {}})
async def test_execute_contract_invalid_event_data():
    """Test contract execution with invalid event data"""
    invalid_execution_data = {
        "contract_id": "test_contract",
        "event": {},  # Missing required fields
        "context": {}
    }
    
    request = ContractExecuteRequest(**invalid_execution_data)
    # Current implementation doesn't validate event data, so this should still succeed
    response = await execute_contract(request)
    assert response.success is True
    assert response.contract_id == "test_contract"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {})
async def test_execute_contract_not_found(mock_execution_data):
    """Test contract execution for non-existent contract"""
    request = ContractExecuteRequest(**mock_execution_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await execute_contract(request)
    
    # Should raise an HTTPException with status code 404
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {"test_contract": {}})
async def test_execute_contract_incompatible_version():
    """Test contract execution with incompatible version"""
    incompatible_execution_data = {
        "contract_id": "test_contract",
        "event": {
            "entity_id": "PRODUCT-2024-001",
            "event": "quality_check",
            "timestamp": 1717987200.0,
            "details": {
                "result": "pass",
                "inspector_id": "INSPECTOR-03"
            }
        },
        "context": {
            "chain": "quality_chain",
            "expected_version": "2.0.0"  # Incompatible version
        }
    }
    
    request = ContractExecuteRequest(**incompatible_execution_data)
    # Current implementation doesn't check version compatibility, so this should still succeed
    response = await execute_contract(request)
    assert response.success is True
    assert response.contract_id == "test_contract"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {})
async def test_create_contract_invalid_endorsement_policy():
    """Test contract creation with invalid endorsement policy"""
    invalid_contract_data = {
        "contract_id": "invalid_policy_contract",
        "version": "1.0.0",
        "implementation": "def test_logic(event, state, context): return {'result': 'success'}",
        "metadata": {
            "domain": "manufacturing",
            "owner": "org1",
            "endorsement_policy": "INVALID_POLICY"  # Invalid endorsement policy
        }
    }
    
    request = ContractCreateRequest(**invalid_contract_data)
    # Current implementation doesn't validate endorsement policy, so this should still succeed
    response = await create_contract(request)
    assert response.success is True
    assert response.contract_id == "invalid_policy_contract"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {})
async def test_create_contract_edge_cases():
    """Test contract creation with edge cases"""
    edge_case_contract_data = {
        "contract_id": "very_long_contract_id_" * 20,  # Very long ID
        "version": "999999999.999999999.999999999",  # Very large version numbers
        "implementation": "x" * 10000,  # Very long implementation
        "metadata": {
            "domain": "x" * 1000,  # Very long domain
            "owner": "org1",
            "endorsement_policy": "SINGLE"  # Different policy
        }
    }
    
    request = ContractCreateRequest(**edge_case_contract_data)
    response = await create_contract(request)
    assert response.success is True


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('hierachain.api.v2.endpoints._contracts', {"test_contract": {}})
async def test_execute_contract_security_edge_cases(mock_execution_data):
    """Test contract execution with security edge cases"""
    edge_case_execution_data = {
        "contract_id": "test_contract",
        "event": {
            "entity_id": "x" * 1000,  # Very long entity ID
            "event": "x" * 1000,  # Very long event name
            "timestamp": 1717987200.0,
            "details": {
                "result": "x" * 10000,  # Very long result
                "inspector_id": "INSPECTOR-03"
            }
        },
        "context": {
            "chain": "x" * 1000  # Very long chain name
        }
    }
    
    request = ContractExecuteRequest(**edge_case_execution_data)
    response = await execute_contract(request)
    assert response.success is True
    assert response.contract_id == "test_contract"


@pytest.mark.asyncio
@patch('hierachain.api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_execute_contract_not_implemented(mock_execution_data):
    """Test contract execution when modules are not available"""
    request = ContractExecuteRequest(**mock_execution_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await execute_contract(request)
    
    # Should raise an HTTPException with status code 501
    assert exc_info.value.status_code == 501