"""
Core types and message definitions for BFT consensus.
"""

import uuid
from typing import Any
from dataclasses import dataclass, field
from enum import Enum


class ConsensusState(Enum):
    """Consensus node states"""

    IDLE = "idle"
    PRE_PREPARED = "pre_prepared"
    PREPARED = "prepared"
    COMMITTED = "committed"
    VIEW_CHANGE = "view_change"


class MessageType(Enum):
    """BFT message types"""

    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    VIEW_CHANGE = "view_change"
    NEW_VIEW = "new_view"


@dataclass
class BFTMessage:
    """BFT consensus message"""

    message_type: MessageType
    view: int
    sequence_number: int
    sender_id: str
    timestamp: float
    signature: str
    data: dict[str, Any] = field(default_factory=dict)
    nonce: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary for serialization"""
        return {
            "message_type": self.message_type.value,
            "view": self.view,
            "sequence_number": self.sequence_number,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "data": self.data,
            "nonce": self.nonce
        }

    def get_signable_payload(self) -> bytes:
        """Get the payload bytes to be signed."""
        # Include critical fields in the signature
        digest = self.data.get("digest") if self.data else None

        # Base payload: Type:View:Seq:Nonce
        payload = (
            f"{self.message_type.value}:"
            f"{self.view}:{self.sequence_number}:{self.nonce}"
        )

        # Add digest if relevant for the message type
        if digest:
            payload += f":{digest}"

        return payload.encode("utf-8")


class ConsensusError(Exception):
    """Exception raised for consensus-related errors"""
