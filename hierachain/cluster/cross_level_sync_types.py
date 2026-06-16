"""Data types for cross-level state synchronisation.

Enums and dataclasses used by CrossLevelSyncManager for
bidirectional sync between MainChain and Sub-chains.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CrossLevelSyncStatus(Enum):
    IDLE = "idle"
    SYNCING_DOWN = "syncing_down"
    SYNCING_UP = "syncing_up"
    VERIFYING = "verifying"
    RESOLVING_CONFLICT = "resolving_conflict"
    COMPLETE = "complete"
    FAILED = "failed"


class SyncDirection(Enum):
    MAINCHAIN_TO_SUBCHAIN = "mainchain_to_subchain"
    SUBCHAIN_TO_MAINCHAIN = "subchain_to_mainchain"
    BIDIRECTIONAL = "bidirectional"


class ConflictResolutionStrategy(Enum):
    MAINCHAIN_WINS = "mainchain_wins"
    SUBCHAIN_WINS = "subchain_wins"
    LATEST_TIMESTAMP = "latest_timestamp"
    MANUAL = "manual"


@dataclass
class SyncConflict:
    conflict_id: str
    source_chain: str
    target_chain: str
    block_index: int
    source_hash: str
    target_hash: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "source_chain": self.source_chain,
            "target_chain": self.target_chain,
            "block_index": self.block_index,
            "source_hash": self.source_hash,
            "target_hash": self.target_hash,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class CrossLevelSyncRequest:
    request_id: str
    source_chain_id: str
    target_chain_id: str
    direction: SyncDirection
    from_block_index: int
    to_block_index: int
    proof_required: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "source_chain_id": self.source_chain_id,
            "target_chain_id": self.target_chain_id,
            "direction": self.direction.value,
            "from_block_index": self.from_block_index,
            "to_block_index": self.to_block_index,
            "proof_required": self.proof_required,
            "timestamp": self.timestamp,
        }


@dataclass
class SyncResult:
    success: bool
    blocks_synced: int = 0
    conflicts_found: int = 0
    conflicts_resolved: int = 0
    error_message: str = ""
    duration_seconds: float = 0.0
    state_root_before: str = ""
    state_root_after: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "blocks_synced": self.blocks_synced,
            "conflicts_found": self.conflicts_found,
            "conflicts_resolved": self.conflicts_resolved,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "state_root_before": self.state_root_before,
            "state_root_after": self.state_root_after,
        }
