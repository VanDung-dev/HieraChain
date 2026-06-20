"""
Ordering storage handler for the HieraChain ordering service.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OrderingStatus(Enum):
    """Ordering service status enumeration"""
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    LOCKDOWN = "lockdown"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class EventStatus(Enum):
    """Event processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    ORDERED = "ordered"
    CERTIFIED = "certified"
    REJECTED = "rejected"


@dataclass
class PendingEvent:
    """Event waiting to be ordered"""
    event_id: str
    event_data: dict[str, Any]
    channel_id: str
    submitter_org: str
    received_at: float
    status: EventStatus
    certification_result: dict[str, Any] | None = None
    signature_verified: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "event_id": self.event_id,
            "event_data": self.event_data,
            "channel_id": self.channel_id,
            "submitter_org": self.submitter_org,
            "received_at": self.received_at,
            "status": self.status.value,
            "certification_result": self.certification_result
        }


@dataclass
class OrderingNode:
    """Ordering service node configuration"""
    node_id: str
    endpoint: str
    is_leader: bool
    weight: float
    status: OrderingStatus
    last_heartbeat: float
    
    def is_healthy(self, timeout: float = 30.0) -> bool:
        """Check if node is healthy based on heartbeat"""
        import time
        return (time.time() - self.last_heartbeat) < timeout
