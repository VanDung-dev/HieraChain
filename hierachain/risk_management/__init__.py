"""
Risk management module for HieraChain Ledger.

Provides comprehensive risk analysis, audit logging, and mitigation
capabilities for identifying and addressing technical and operational risks.
"""

from hierachain.risk_management.types import (
    RiskSeverity,
    RiskCategory,
    RiskAssessment,
    MitigationStatus,
    MitigationAction,
    MitigationResult,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditFilter,
)

from hierachain.risk_management.risk_analyzer import (
    RiskAnalyzer,
)

from hierachain.risk_management.mitigation_strategies import (
    MitigationManager,
    ConsensusMitigationStrategies,
    SecurityMitigationStrategies,
    PerformanceMitigationStrategies,
    StorageMitigationStrategies,
    renew_certificates,
    implement_rate_limiting,
    scale_processing_capacity,
    optimize_memory_usage,
    execute_backup,
    implement_state_pruning,
)

from hierachain.risk_management.audit_logger import (
    AuditLogger,
    AuditStorage,
    ArrowAuditStorage,
    FileAuditStorage,
    RotatingAuditStorage,
    DatabaseAuditStorage,
    verify_integrity,
)

__all__ = [
    # Risk Analysis
    'RiskAnalyzer',
    'RiskAssessment',
    'RiskCategory',
    'RiskSeverity',
    # Mitigation Strategies
    'MitigationManager',
    'MitigationStatus',
    'MitigationAction',
    'MitigationResult',
    'ConsensusMitigationStrategies',
    'SecurityMitigationStrategies',
    'PerformanceMitigationStrategies',
    'StorageMitigationStrategies',
    'renew_certificates',
    'implement_rate_limiting',
    'scale_processing_capacity',
    'optimize_memory_usage',
    'execute_backup',
    'implement_state_pruning',
    # Audit Logger
    'AuditLogger',
    'AuditEvent',
    'AuditEventType',
    'AuditSeverity',
    'AuditFilter',
    'AuditStorage',
    'ArrowAuditStorage',
    'FileAuditStorage',
    'RotatingAuditStorage',
    'DatabaseAuditStorage',
    'verify_integrity',
]
