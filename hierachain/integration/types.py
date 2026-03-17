"""
Shared types for HieraChain Integration.

This module defines common data structures used by integration clients.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Transaction:
    """Transaction to submit to Engine."""
    tx_id: str
    entity_id: str
    event_type: str
    arrow_payload: bytes = b""
    signature: str = ""
    timestamp: float = field(default_factory=time.time)
    details: dict[str, str] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result of batch transaction processing."""
    success: bool
    message: str
    processed_tx_ids: list[str]
    processing_time_ms: int
    errors: list[dict[str, str]]


@dataclass
class TxStatus:
    """Status of a transaction."""
    tx_id: str
    status: str  # "PENDING", "CONFIRMED", "FAILED"
    timestamp: int
    block_hash: str = ""


@dataclass
class HealthResponse:
    """Health status of the Engine."""
    healthy: bool
    version: str
    uptime_seconds: int
    stats: dict[str, Any]
