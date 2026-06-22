"""
Event creation helper functions for domain-specific events.
"""

from hierachain.domains.events.custom_events import (
    ResourceAllocationEvent,
    QualityCheckEvent,
    StatusUpdateEvent,
    ApprovalEvent,
    ComplianceEvent,
)


def create_resource_allocation(
    entity_id: str,
    resource_type: str,
    resource_id: str,
    allocation_type: str = "assigned",
    domain_type: str = "generic",
    **kwargs
) -> ResourceAllocationEvent:
    """Create a resource allocation event."""
    return ResourceAllocationEvent(
        entity_id=entity_id,
        resource_type=resource_type,
        resource_id=resource_id,
        allocation_type=allocation_type,
        domain_type=domain_type,
        **kwargs
    )


def create_quality_check(
    entity_id: str,
    check_type: str,
    check_result: str,
    domain_type: str = "generic",
    **kwargs
) -> QualityCheckEvent:
    """Create a quality check event."""
    return QualityCheckEvent(
        entity_id=entity_id,
        check_type=check_type,
        check_result=check_result,
        domain_type=domain_type,
        **kwargs
    )


def create_status_update(
    entity_id: str,
    old_status: str,
    new_status: str,
    domain_type: str = "generic",
    **kwargs
) -> StatusUpdateEvent:
    """Create a status update event."""
    return StatusUpdateEvent(
        entity_id=entity_id,
        old_status=old_status,
        new_status=new_status,
        domain_type=domain_type,
        **kwargs
    )


def create_approval(
    entity_id: str,
    approval_type: str,
    approval_status: str,
    approver_id: str,
    domain_type: str = "generic",
    **kwargs
) -> ApprovalEvent:
    """Create an approval event."""
    return ApprovalEvent(
        entity_id=entity_id,
        approval_type=approval_type,
        approval_status=approval_status,
        approver_id=approver_id,
        domain_type=domain_type,
        **kwargs
    )


def create_compliance_check(
    entity_id: str,
    compliance_type: str,
    compliance_status: str,
    domain_type: str = "generic",
    **kwargs
) -> ComplianceEvent:
    """Create a compliance event."""
    return ComplianceEvent(
        entity_id=entity_id,
        compliance_type=compliance_type,
        compliance_status=compliance_status,
        domain_type=domain_type,
        **kwargs
    )
