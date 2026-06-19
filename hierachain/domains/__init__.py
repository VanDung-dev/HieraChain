"""
Package root — re-exports chains, events, and utils for backward compatibility.
"""

from hierachain.domains.chains import BaseChain, DomainChain
from hierachain.domains.events import (
    BaseEvent, DomainEvent,
    ResourceAllocationEvent, QualityCheckEvent,
    StatusUpdateEvent, ApprovalEvent, ComplianceEvent,
    create_resource_allocation, create_quality_check,
    create_status_update, create_approval, create_compliance_check,
)
from hierachain.domains.utils import EntityTracer, CrossChainValidator


__all__ = [
    "BaseChain",
    "DomainChain",
    "BaseEvent",
    "DomainEvent",
    "EntityTracer",
    "CrossChainValidator",
]
