"""
HieraChain SDK — Shared types, models, and value objects.

Dataclasses and enums used by both sync and async clients.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class HieraChainClientConfig:
    """Configuration for HieraChain client."""
    base_url: str = "http://localhost:2661"
    timeout: float = 30.0
    max_retries: int = 5
    initial_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 30.0
    api_key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for fail-fast behavior.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject immediately
    - HALF_OPEN: Testing if service recovered
    """
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker opened after %d failures",
                self._failure_count
            )

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True
        return False

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0


@dataclass
class EventResult:
    """Result of submitting an event."""
    event_id: str
    status: str
    message: str = ""


@dataclass
class NodeStatus:
    """Status of the HieraChain node (API v3)."""
    status: str
    version: str
    chains_active: int
    license_active: bool
    uptime: str


@dataclass
class ChainStats:
    """Statistics for a specific chain."""
    chain_name: str
    total_blocks: int
    total_events: int
    unique_entities: int = 0
    proof_count: int | None = None
    registered_sub_chains: int | None = None


@dataclass
class EntityTrace:
    """Trace result for an entity."""
    entity_id: str
    chains: list[str]
    events: list[dict[str, Any]]
