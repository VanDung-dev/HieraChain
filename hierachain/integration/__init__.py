"""
Integration module for HieraChain framework.
"""

from hierachain.integration.enterprise import (
    EnterpriseIntegration,
    BaseERPIntegration,
    SAPIntegration,
    OracleIntegration,
    DynamicsIntegration,
    IntegrationError
)

from hierachain.integration.go_client import (
    GoEngineClient,
    GoEngineClientSync,
    GoEngineError,
    GoEngineConnectionError,
    GoEngineUnavailableError,
    Transaction,
    BatchResult,
    TxStatus,
    HealthResponse,
)

__all__ = [
    'EnterpriseIntegration',
    'BaseERPIntegration',
    'SAPIntegration',
    'OracleIntegration',
    'DynamicsIntegration',
    'IntegrationError',
    'GoEngineClient',
    'GoEngineClientSync',
    'GoEngineError',
    'GoEngineConnectionError',
    'GoEngineUnavailableError',
    'Transaction',
    'BatchResult',
    'TxStatus',
    'HealthResponse',
]