"""
Shared types for the Channel package.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ChannelStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    MAINTENANCE = "maintenance"


@dataclass
class Organization:
    org_id: str
    name: str
    msp_id: str
    endpoints: list[str]
    certificates: dict[str, Any]
    roles: set[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles
