"""
Contract lifecycle management for HieraChain Ledger.

Defines contract statuses, event types, lifecycle transitions,
and the ContractLifecycle manager.
"""

import time
from typing import Any
from enum import Enum


class ContractStatus(Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class ContractEventType(Enum):
    DEPLOYED = "deployed"
    ACTIVATED = "activated"
    EXECUTED = "executed"
    UPGRADED = "upgraded"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    ERROR = "error"


class ContractLifecycle:
    def __init__(self) -> None:
        self.status = ContractStatus.DEVELOPMENT
        self.status_history: list[dict[str, Any]] = []
        self.deployment_info: dict[str, Any] | None = None
        self.deprecation_info: dict[str, Any] | None = None

    def transition_to(
        self,
        new_status: ContractStatus,
        reason: str = "",
        metadata: dict[str, Any] | None = None
    ) -> bool:
        if not is_valid_status_transition(self.status, new_status):
            return False
        status_change = {
            "timestamp": time.time(),
            "from_status": self.status.value,
            "to_status": new_status.value,
            "reason": reason,
            "metadata": metadata or {}
        }
        self.status_history.append(status_change)
        self.status = new_status
        if new_status == ContractStatus.ACTIVE and not self.deployment_info:
            md = metadata or {}
            self.deployment_info = {
                "deployed_at": time.time(),
                "deployed_by": md.get("deployed_by", "system"),
                "deployment_metadata": md
            }
        elif new_status == ContractStatus.DEPRECATED and not self.deprecation_info:
            md = metadata or {}
            self.deprecation_info = {
                "deprecated_at": time.time(),
                "deprecated_by": md.get("deprecated_by", "system"),
                "deprecation_reason": reason,
                "end_of_life_date": md.get("end_of_life_date")
            }
        return True

    def get_status_info(self) -> dict[str, Any]:
        return {
            "current_status": self.status.value,
            "status_history": self.status_history,
            "deployment_info": self.deployment_info,
            "deprecation_info": self.deprecation_info
        }


def is_valid_status_transition(
    from_status: ContractStatus, to_status: ContractStatus
) -> bool:
    valid_transitions = {
        ContractStatus.DEVELOPMENT: [ContractStatus.TESTING, ContractStatus.DISABLED],
        ContractStatus.TESTING: [
            ContractStatus.ACTIVE,
            ContractStatus.DEVELOPMENT,
            ContractStatus.DISABLED
        ],
        ContractStatus.ACTIVE: [ContractStatus.DEPRECATED, ContractStatus.DISABLED],
        ContractStatus.DEPRECATED: [ContractStatus.DISABLED, ContractStatus.ARCHIVED],
        ContractStatus.DISABLED: [ContractStatus.DEVELOPMENT, ContractStatus.ARCHIVED],
        ContractStatus.ARCHIVED: []
    }
    return to_status in valid_transitions.get(from_status, [])
