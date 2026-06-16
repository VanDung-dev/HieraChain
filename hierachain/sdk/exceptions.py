"""
HieraChain SDK — Custom exception classes.

All exceptions raised by the sync and async clients.
"""

from __future__ import annotations


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class HieraChainAPIError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ServiceUnavailableError(HieraChainAPIError):
    """Service returned 503 - system overloaded or in lockdown."""
    pass


class LockdownError(HieraChainAPIError):
    """Node is in lockdown mode."""
    pass
