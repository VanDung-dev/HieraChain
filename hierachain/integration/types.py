"""
Shared types for HieraChain Integration.

This module defines common data structures used by integration clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IntegrationError(Exception):
    """Exception raised for integration-related errors"""
    pass


class MappingError(Exception):
    """Exception raised for mapping-related errors"""
    pass


class SyncStatus(Enum):
    """Synchronization status"""
    IDLE = "idle"
    SYNCING = "syncing"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class SyncResult:
    """Result of a synchronization operation"""
    profile_name: str
    status: SyncStatus
    events_processed: int
    errors: list[str] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        """Get sync duration in seconds"""
        return self.end_time - self.start_time if self.end_time > 0 else 0.0



