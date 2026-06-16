"""
Shared types for HieraChain Hierarchical Module.

This module defines common data structures used across the hierarchical
module, including exceptions, enums, and dataclasses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OrganizationError(Exception):
    """Exception raised for organization-related errors"""
    pass


class NetworkError(Exception):
    """Exception raised for network-related errors"""
    pass


class ConsensusError(Exception):
    """Exception raised for consensus-related errors"""
    pass


class TransactionState(str, Enum):
    """States for a cross-chain transaction."""

    PENDING = "pending"
    PREPARED = "prepared"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class CrossChainTransaction:
    """Represents a cross-chain transaction."""

    transaction_id: str
    source_chain: str
    destination_chain: str
    payload: dict[str, Any]
    state: TransactionState = TransactionState.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: str | None = None
