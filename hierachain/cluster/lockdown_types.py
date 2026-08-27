"""Lockdown data types for the cluster lockdown protocol.

Dataclasses and enums used by ClusterLockdownManager for
cluster-wide lockdown coordination.
"""

import hashlib
import hmac
from dataclasses import dataclass, field
from enum import Enum


class LockdownMessageType(Enum):
    LOCKDOWN = "lockdown"
    RECOVERY = "recovery"
    HEARTBEAT = "heartbeat"
    LOCKDOWN_VOTE = "lockdown_vote"
    RECOVERY_VOTE = "recovery_vote"
    QUARANTINE_REPORT = "quarantine_report"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"


@dataclass
class LockdownMessage:
    node_id: str
    timestamp: float
    reason: str
    message_type: LockdownMessageType
    signature: str = ""

    def to_dict(self) -> dict:
        return {
            "msg_type": "cluster_lockdown",
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "lockdown_type": self.message_type.value,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LockdownMessage":
        return cls(
            node_id=data.get("node_id", "unknown"),
            timestamp=data.get("timestamp", 0.0),
            reason=data.get("reason", ""),
            message_type=LockdownMessageType(data.get("lockdown_type", "lockdown")),
            signature=data.get("signature", ""),
        )

    def compute_signature(self, secret_key: str) -> str:
        message_data = f"{self.node_id}:{self.timestamp}:{self.reason}:{self.message_type.value}"
        return hmac.new(
            secret_key.encode(), message_data.encode(), hashlib.sha256
        ).hexdigest()

    def verify_signature(self, secret_key: str) -> bool:
        if not isinstance(self.signature, str) or not self.signature:
            return False
        expected = self.compute_signature(secret_key)
        try:
            return hmac.compare_digest(self.signature, expected) or hmac.compare_digest(
                self.signature, expected[:32]
            )
        except (TypeError, ValueError):
            return False


@dataclass
class ClusterState:
    is_locked: bool = False
    locked_by: str = ""
    lock_reason: str = ""
    lock_timestamp: float = 0.0
    locked_nodes: set = field(default_factory=set)


@dataclass
class QuarantineReport:
    node_id: str
    timestamp: float
    pending_event_ids: list = field(default_factory=list)
    last_block_index: int = 0
    last_block_hash: str = ""
    total_pending: int = 0
    signature: str = ""

    def to_dict(self) -> dict:
        return {
            "msg_type": "cluster_lockdown",
            "lockdown_type": LockdownMessageType.QUARANTINE_REPORT.value,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "pending_event_ids": self.pending_event_ids,
            "last_block_index": self.last_block_index,
            "last_block_hash": self.last_block_hash,
            "total_pending": self.total_pending,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuarantineReport":
        return cls(
            node_id=data.get("node_id", "unknown"),
            timestamp=data.get("timestamp", 0.0),
            pending_event_ids=data.get("pending_event_ids", []),
            last_block_index=data.get("last_block_index", 0),
            last_block_hash=data.get("last_block_hash", ""),
            total_pending=data.get("total_pending", 0),
            signature=data.get("signature", ""),
        )

    def compute_signature(self, secret_key: str) -> str:
        msg = f"{self.node_id}:{self.timestamp}:{self.last_block_index}"
        return hmac.new(
            secret_key.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()[:32]

    def verify_signature(self, secret_key: str) -> bool:
        return hmac.compare_digest(self.signature, self.compute_signature(secret_key))
