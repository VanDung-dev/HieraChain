"""
Shared types for the rollback manager module.
"""

from __future__ import annotations

import time
from typing import Any, Optional
from enum import Enum, auto
from dataclasses import dataclass, asdict


class RollbackStrategy(Enum):
    FULL = auto()
    PARTIAL = auto()
    SELECTIVE = auto()


class RollbackLevel(Enum):
    CHAIN = auto()
    BLOCK = auto()
    EVENT = auto()


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


class RollbackResult:
    def __init__(
        self,
        success: bool,
        chain_id: Optional[str] = None,
        strategy: Optional[RollbackStrategy] = None,
        level: Optional[RollbackLevel] = None,
        restored_events: int = 0,
        affected_events: int = 0,
        error_message: str = "",
        rollback_id: str = "",
        start_time: float = 0.0,
        chain_operation_times: Optional[dict[str, float]] = None,
        duration: float = 0.0,
    ) -> None:
        self.success = success
        self.chain_id = chain_id
        self.strategy = strategy
        self.level = level
        self.restored_events = restored_events
        self.affected_events = affected_events
        self.error_message = error_message
        self.rollback_id = rollback_id
        self.start_time = start_time
        self.chain_operation_times = chain_operation_times or {}
        self.duration = duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollback_id": self.rollback_id,
            "chain_id": self.chain_id or "",
            "strategy": self.strategy.name if self.strategy else "",
            "level": self.level.name if self.level else "",
            "success": self.success,
            "restored_events": self.restored_events,
            "affected_events": self.affected_events,
            "error": self.error_message,
            "target_time": self.start_time,
            "chain_operation_times": self.chain_operation_times,
            "duration": self.duration,
        }


def format_rollback_result(result: RollbackResult) -> str:
    return (
        f"Rollback {result.rollback_id}: "
        f"{'SUCCESS' if result.success else 'FAILED'}, "
        f"chain={result.chain_id}, "
        f"strategy={result.strategy.name if result.strategy else 'N/A'}, "
        f"level={result.level.name if result.level else 'N/A'}, "
        f"restored_events={result.restored_events}, "
        f"affected_events={result.affected_events}"
        f"{', error=' + result.error_message if result.error_message else ''}"
    )


def create_rollback_result(
    success: bool,
    chain_id: str = "",
    strategy: Optional[RollbackStrategy] = None,
    level: Optional[RollbackLevel] = None,
    restored_events: int = 0,
    affected_events: int = 0,
    error_message: str = "",
    start_time: float = 0.0,
    chain_operation_times: Optional[dict[str, float]] = None,
    duration: float = 0.0,
) -> RollbackResult:
    return RollbackResult(
        success=success,
        chain_id=chain_id,
        strategy=strategy,
        level=level,
        restored_events=restored_events,
        affected_events=affected_events,
        error_message=error_message,
        rollback_id=f"rb_{int(time.time() * 1_000_000)}",
        start_time=start_time,
        chain_operation_times=chain_operation_times,
        duration=duration,
    )
