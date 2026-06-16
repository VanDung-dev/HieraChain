"""
Error mitigation module for HieraChain Ledger.

This module provides comprehensive error mitigation capabilities including:
- Data validation
- Error classification and risk assessment
- Transaction journaling for durability
- Recovery engines for network, consensus, and auto-scaling
- Rollback management and state snapshots
- Validators for consensus, encryption, resources, and APIs
"""

# Data validation
from hierachain.error_mitigation.data_validator import (
    DataValidator,
    ValidationLevel,
    ValidationResult,
    validate_consistency,
    validate_and_fix_events,
    create_strict_validator,
    create_lenient_validator,
)

# Error classification
from hierachain.error_mitigation.error_classifier import (
    ErrorClassifier,
    get_priority_score,
    classify_error_quick,
    get_priority_threshold,
)
from hierachain.error_mitigation.classifier_types import (
    ErrorCategory,
    PriorityLevel,
    ImpactLevel,
    LikelihoodLevel,
    ErrorInfo,
)
from hierachain.error_mitigation.risk_matrix import RiskPriorityMatrix

# Transaction journal
from hierachain.error_mitigation.journal import TransactionJournal

# Recovery engine
from hierachain.error_mitigation.recovery_engine import (
    RecoveryError,
    NetworkRecoveryEngine,
    AutoScaler,
    ConsensusRecoveryEngine,
    BackupRecoveryEngine,
)

# Rollback manager
from hierachain.error_mitigation.rollback_manager import (
    RollbackManager,
)
from hierachain.error_mitigation.rollback_types import (
    RollbackType,
    RollbackStatus,
    StateSnapshot,
    RollbackOperation,
    RollbackStrategy,
    RollbackLevel,
    RollbackResult,
)

# Validators
from hierachain.error_mitigation.consensus_validator import ConsensusValidator
from hierachain.error_mitigation.encryption_validator import EncryptionValidator
from hierachain.error_mitigation.resource_validator import ResourceValidator
from hierachain.error_mitigation.validator import (
    APIValidator,
    ValidationError,
    ConfigurationError,
    SecurityError,
    validate_certificate,
)

__all__ = [
    # Data validation
    "DataValidator",
    "ValidationLevel",
    "ValidationResult",
    "validate_consistency",
    "validate_and_fix_events",
    "create_strict_validator",
    "create_lenient_validator",
    # Error classification
    "ErrorClassifier",
    "ErrorCategory",
    "PriorityLevel",
    "ImpactLevel",
    "LikelihoodLevel",
    "ErrorInfo",
    "RiskPriorityMatrix",
    "get_priority_score",
    "classify_error_quick",
    "get_priority_threshold",
    # Transaction journal
    "TransactionJournal",
    # Recovery engine
    "RecoveryError",
    "NetworkRecoveryEngine",
    "AutoScaler",
    "ConsensusRecoveryEngine",
    "BackupRecoveryEngine",
    # Rollback manager
    "RollbackManager",
    "RollbackType",
    "RollbackStatus",
    "StateSnapshot",
    "RollbackOperation",
    "RollbackStrategy",
    "RollbackLevel",
    "RollbackResult",
    # Validators
    "ConsensusValidator",
    "EncryptionValidator",
    "ResourceValidator",
    "APIValidator",
    "ValidationError",
    "ConfigurationError",
    "SecurityError",
    "validate_certificate",
]
