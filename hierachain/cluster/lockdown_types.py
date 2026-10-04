"""Dataclasses and enums for cluster lockdown messages and reports."""

import hashlib
import hmac
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from hierachain.serialization import dumps_canonical_json


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
        """Authenticate only; dispatchers must also use LockdownMessageGuard.accept()."""
        if (
            not isinstance(self.signature, str) or not self.signature
            or not isinstance(secret_key, str) or not secret_key
            or not isinstance(self.message_type, LockdownMessageType)
        ):
            return False
        try:
            expected = self.compute_signature(secret_key)
            return hmac.compare_digest(self.signature, expected) or hmac.compare_digest(
                self.signature, expected[:32]
            )
        except (TypeError, ValueError):
            return False


class LockdownMessageGuard:
    """Process-local, bounded admission gate for authenticated lockdown messages.

    Keep one guard per dispatcher, across requests. Capacity exhaustion rejects
    new messages until records expire; it never evicts an unexpired replay record.
    """

    def __init__(
        self, max_age: float = 60.0, future_skew: float = 5.0,
        max_entries: int = 10000, clock: Callable[[], float] = time.time,
    ) -> None:
        if (
            not math.isfinite(max_age) or max_age <= 0
            or not math.isfinite(future_skew) or future_skew < 0
            or not isinstance(max_entries, int) or max_entries <= 0
        ):
            raise ValueError("Invalid lockdown admission limits")
        self.max_age = max_age
        self.future_skew = future_skew
        self.max_entries = max_entries
        self._clock = clock
        self._seen: dict[str, float] = {}
        self._latest_time = float("-inf")
        self._lock = threading.Lock()

    def accept(self, message: LockdownMessage, secret_key: str) -> bool:
        """Authenticate and atomically consume a fresh message exactly once."""
        if (
            not isinstance(message.timestamp, (int, float))
            or isinstance(message.timestamp, bool) or not math.isfinite(message.timestamp)
            or not isinstance(message.message_type, LockdownMessageType)
            or not isinstance(message.node_id, str) or not message.node_id
            or not isinstance(message.reason, str)
            or not isinstance(secret_key, str) or not secret_key
            or not message.verify_signature(secret_key)
        ):
            return False
        # Canonical HMAC identifies both full and legacy truncated signatures.
        identity = message.compute_signature(secret_key)
        with self._lock:
            now = self._clock()
            if not math.isfinite(now):
                return False
            # A wall-clock rollback must not resurrect expired replay records.
            now = max(now, self._latest_time)
            self._latest_time = now
            if not now - self.max_age <= message.timestamp <= now + self.future_skew:
                return False
            self._seen = {key: expiry for key, expiry in self._seen.items() if expiry >= now}
            if identity in self._seen or len(self._seen) >= self.max_entries:
                return False
            self._seen[identity] = message.timestamp + self.max_age
            return True


@dataclass
class QuarantineReport:
    node_id: str
    timestamp: float
    pending_event_ids: list[str] = field(default_factory=list)
    last_block_index: int = 0
    last_block_hash: str = ""
    total_pending: int = 0
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "QuarantineReport":
        if (
            data.get("msg_type", "cluster_lockdown") != "cluster_lockdown"
            or data.get("lockdown_type", LockdownMessageType.QUARANTINE_REPORT.value)
            != LockdownMessageType.QUARANTINE_REPORT.value
        ):
            raise ValueError("Invalid quarantine report message type")
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
        """Sign every serialized field except signature, preserving list order."""
        if not math.isfinite(self.timestamp):
            raise ValueError("Quarantine report timestamp must be finite")
        payload = self.to_dict()
        payload.pop("signature")
        msg = dumps_canonical_json(payload)
        return hmac.new(
            secret_key.encode(), msg, hashlib.sha256
        ).hexdigest()[:32]

    def verify_signature(self, secret_key: str) -> bool:
        if not isinstance(self.signature, str) or not self.signature:
            return False
        try:
            return hmac.compare_digest(self.signature, self.compute_signature(secret_key))
        except (TypeError, ValueError):
            return False
