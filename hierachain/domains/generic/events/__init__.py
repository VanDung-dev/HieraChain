"""
Backward-compat re-export shim — prefer `hierachain.domains.events` imports.
"""

from hierachain.domains.events import (
    BaseEvent, DomainEvent,
    ResourceAllocationEvent, QualityCheckEvent,
    StatusUpdateEvent, ApprovalEvent, ComplianceEvent,
    create_resource_allocation, create_quality_check,
    create_status_update, create_approval, create_compliance_check,
)


__all__ = [
    "BaseEvent", "DomainEvent",
    "ResourceAllocationEvent", "QualityCheckEvent",
    "StatusUpdateEvent", "ApprovalEvent", "ComplianceEvent",
    "create_resource_allocation", "create_quality_check",
    "create_status_update", "create_approval", "create_compliance_check",
]
