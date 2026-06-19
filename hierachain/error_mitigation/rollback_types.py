"""
Shared types for the rollback manager module.
"""

from __future__ import annotations

from typing import Any
from enum import Enum
from dataclasses import dataclass, asdict


class RollbackType(Enum):
    CONFIGURATION = "configuration"
    CHAIN_STATE = "chain_state"
    CONSENSUS_STATE = "consensus_state"
    STORAGE_STATE = "storage_state"
    FULL_SYSTEM = "full_system"


class RollbackStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StateSnapshot:
    snapshot_id: str
    snapshot_type: RollbackType
    timestamp: float
    description: str
    data_hash: str
    data_path: str
    metadata: dict[str, Any]
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateSnapshot:
        return cls(**data)


@dataclass
class RollbackOperation:
    operation_id: str
    rollback_type: RollbackType
    target_snapshot: StateSnapshot
    status: RollbackStatus
    start_time: float
    end_time: float | None
    error_message: str | None
    rollback_steps: list[str]
    affected_components: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['rollback_type'] = self.rollback_type.value
        data['status'] = self.status.value
        data['target_snapshot'] = self.target_snapshot.to_dict()
        return data
