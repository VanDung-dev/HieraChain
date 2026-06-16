"""
Error classification types for HieraChain Ledger.

Defines enums and data structures for error classification.
"""

from typing import Any
from enum import Enum
from dataclasses import dataclass


class PriorityLevel(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class ErrorCategory(Enum):
    CONSENSUS = "consensus"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STORAGE = "storage"
    NETWORK = "network"
    API = "api"
    OPERATIONAL = "operational"


class ImpactLevel(Enum):
    CATASTROPHIC = 5
    MAJOR = 4
    MODERATE = 3
    MINOR = 2
    NEGLIGIBLE = 1


class LikelihoodLevel(Enum):
    VERY_HIGH = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    VERY_LOW = 1


@dataclass
class ErrorInfo:
    error_id: str
    error_type: str
    category: ErrorCategory
    priority: PriorityLevel
    impact: ImpactLevel
    likelihood: LikelihoodLevel
    description: str
    mitigation_strategy: str
    timestamp: float
    metadata: dict[str, Any]
