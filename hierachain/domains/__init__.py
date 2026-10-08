"""
Package root — re-exports chains, events, and utils for backward compatibility.
"""

from hierachain.domains.chains import BaseChain, DomainChain
from hierachain.domains.events import (
    ApprovalEvent,
    BaseEvent,
    ComplianceEvent,
    DomainEvent,
    QualityCheckEvent,
    ResourceAllocationEvent,
    StatusUpdateEvent,
    create_approval,
    create_compliance_check,
    create_quality_check,
    create_resource_allocation,
    create_status_update,
)
from hierachain.domains.utils import CrossChainValidator, EntityTracer

__all__ = [
    "BaseChain",
    "BaseEvent",
    "CrossChainValidator",
    "DomainChain",
    "DomainEvent",
    "EntityTracer",
]
