"""
Shared types for the Rebalancer package.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time


class RebalanceStatus(Enum):
    IDLE = "idle"
    MONITORING = "monitoring"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    SPLITTING = "splitting"
    MIGRATING = "migrating"
    COMPLETE = "complete"
    COOLDOWN = "cooldown"
    FAILED = "failed"


class SplitStrategy(Enum):
    HASH_BASED = "hash_based"
    TIME_BASED = "time_based"
    ROUND_ROBIN = "round_robin"
    LOAD_BASED = "load_based"


@dataclass
class RebalanceMetrics:
    sub_chain_id: str
    current_eps: float = 0.0
    avg_eps: float = 0.0
    peak_eps: float = 0.0
    event_count: int = 0
    block_count: int = 0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    last_split_time: float = 0.0
    splits_total: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_chain_id": self.sub_chain_id,
            "current_eps": self.current_eps,
            "avg_eps": self.avg_eps,
            "peak_eps": self.peak_eps,
            "event_count": self.event_count,
            "block_count": self.block_count,
            "memory_mb": self.memory_mb,
            "cpu_percent": self.cpu_percent,
            "last_split_time": self.last_split_time,
            "splits_total": self.splits_total,
            "timestamp": self.timestamp,
        }


@dataclass
class SplitResult:
    success: bool
    parent_chain_id: str
    child_chain_ids: list[str] = field(default_factory=list)
    events_migrated: int = 0
    blocks_migrated: int = 0
    duration_seconds: float = 0.0
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "parent_chain_id": self.parent_chain_id,
            "child_chain_ids": self.child_chain_ids,
            "events_migrated": self.events_migrated,
            "blocks_migrated": self.blocks_migrated,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }
