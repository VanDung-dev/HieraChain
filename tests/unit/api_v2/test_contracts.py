"""
Unit tests for Contract API endpoints in v2

This module contains unit tests for the contract-related endpoints in API v2,
including contract creation and execution.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from api.v2.endpoints import create_contract, execute_contract
from api.v2.schemas import ContractCreateRequest, ContractExecuteRequest


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
@patch('api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('api.v2.endpoints._contracts', {})
async def test_create_contract_success(mock_contract_data):
    """Test successful contract creation"""
    request = ContractCreateRequest(**mock_contract_data)
    response = await create_contract(request)
    
    assert response.success is True
    assert response.contract_id == "test_contract"


@pytest.mark.asyncio
@patch('api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_create_contract_not_implemented(mock_contract_data):
    """Test contract creation when modules are not available"""
    request = ContractCreateRequest(**mock_contract_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await create_contract(request)
    
    # Should raise an HTTPException with status code 501
    assert exc_info.value.status_code == 501


@pytest.mark.asyncio
@patch('api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('api.v2.endpoints._contracts', {"test_contract": {}})
async def test_execute_contract_success(mock_execution_data):
    """Test successful contract execution"""
    request = ContractExecuteRequest(**mock_execution_data)
    response = await execute_contract(request)
    
    assert response.success is True
    assert response.contract_id == "test_contract"
    assert response.result is not None


@pytest.mark.asyncio
@patch('api.v2.endpoints.HAS_NEW_MODULES', True)
@patch('api.v2.endpoints._contracts', {})
async def test_execute_contract_not_found(mock_execution_data):
    """Test contract execution for non-existent contract"""
    request = ContractExecuteRequest(**mock_execution_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await execute_contract(request)
    
    # Should raise an HTTPException with status code 404
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch('api.v2.endpoints.HAS_NEW_MODULES', False)
async def test_execute_contract_not_implemented(mock_execution_data):
    """Test contract execution when modules are not available"""
    request = ContractExecuteRequest(**mock_execution_data)
    
    with pytest.raises(HTTPException) as exc_info:
        await execute_contract(request)
    
    # Should raise an HTTPException with status code 501
    assert exc_info.value.status_code == 501