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
    ErrorCategory,
    PriorityLevel,
    ImpactLevel,
    LikelihoodLevel,
    ErrorInfo,
    RiskPriorityMatrix,
    get_priority_score,
)

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
    RollbackType,
    RollbackStatus,
    StateSnapshot,
    RollbackOperation,
)

# Validators
from hierachain.error_mitigation.validator import (
    ConsensusValidator,
    EncryptionValidator,
    ResourceValidator,
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
