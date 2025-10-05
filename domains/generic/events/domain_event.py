"""
Domain Event implementations for Hierarchical-Blockchain Framework.

This module provides concrete domain-specific event implementations that extend
the base event classes for common business scenarios. These events follow
framework guidelines and can be used as templates for custom domain implementations.
"""

import time
from typing import Dict, Any, Optional
from .base_event import BaseEvent


class DomainEvent(BaseEvent):
    """
    Generic domain event that can be customized for specific business domains.
    
    This class provides a flexible foundation for domain-specific events
    while maintaining compliance with framework guidelines.
    """
    
    def __init__(self, entity_id: str, event_type: str, domain_type: str,
                 details: Optional[Dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize a domain event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            event_type: Type of event
            domain_type: Domain this event belongs to
            details: Additional event details
            timestamp: Event timestamp (defaults to current time)
        """
        self.domain_type = domain_type
        
        # Add domain info to details
        domain_details = details or {}
        domain_details["domain_type"] = domain_type
        
        super().__init__(entity_id, event_type, domain_details, timestamp)
    
    def validate_domain_specific(self) -> bool:
        """
        Validate domain event requirements.
        
        Returns:
            True if domain event is valid, False otherwise
        """
        # Check domain type is specified
        if not self.domain_type or not isinstance(self.domain_type, str):
            return False
        
        # Domain type should be in details
        if self.details.get("domain_type") != self.domain_type:
            return False
        
        return True


class ResourceAllocationEvent(DomainEvent):
    """
    Event for resource allocation operations in business domains.
    
    This event type is commonly used across various business domains
    for tracking resource assignments and allocations.
    """
    
    def __init__(self, entity_id: str, resource_type: str, resource_id: str,
                 allocation_type: str = "assigned", domain_type: str = "generic",
                 details: Optional[Dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize a resource allocation event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            resource_type: Type of resource being allocated
            resource_id: Identifier of the specific resource
            allocation_type: Type of allocation (assigned, released, reserved)
            domain_type: Domain this event belongs to
            details: Additional event details
            timestamp: Event timestamp (defaults to current time)
        """
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.allocation_type = allocation_type
        
        # Create event type
        event_type = f"resource_{allocation_type}"
        
        # Add resource info to details
        resource_details = details or {}
        resource_details.update({
            "resource_type": resource_type,
            "resource_id": resource_id,
            "allocation_type": allocation_type
        })
        
        super().__init__(entity_id, event_type, domain_type, resource_details, timestamp)
    
    def validate_domain_specific(self) -> bool:
        """
        Validate resource allocation event requirements.
        
        Returns:
            True if resource allocation event is valid, False otherwise
        """
        # Use parent validation first
        if not super().validate_domain_specific():
            return False
        
        # Check allocation type is valid
        valid_allocations = ["assigned", "released", "reserved", "transferred"]
        if self.allocation_type not in valid_allocations:
            return False
        
        # Check resource identifiers
        if not self.resource_type or not isinstance(self.resource_type, str):
            return False
        
        if not self.resource_id or not isinstance(self.resource_id, str):
            return False
        
        return True


class QualityCheckEvent(DomainEvent):
    """
    Event for quality check operations in business domains.
    
    This event type is used for tracking quality assurance,
    inspections, and validation processes.
    """
    
    def __init__(self, entity_id: str, check_type: str, check_result: str,
                 inspector_id: Optional[str] = None, domain_type: str = "generic",
                 details: Optional[Dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize a quality check event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            check_type: Type of quality check performed
            check_result: Result of the quality check (passed, failed, pending)
            inspector_id: Identifier of the inspector/checker
            domain_type: Domain this event belongs to
            details: Additional event details
            timestamp: Event timestamp (defaults to current time)
        """
        self.check_type = check_type
        self.check_result = check_result
        self.inspector_id = inspector_id
        
        # Create event type
        event_type = "quality_check"
        
        # Add quality check info to details
        quality_details = details or {}
        quality_details.update({
            "check_type": check_type,
            "check_result": check_result,
            "inspector_id": inspector_id
        })
        
        super().__init__(entity_id, event_type, domain_type, quality_details, timestamp)
    
    def validate_domain_specific(self) -> bool:
        """
        Validate quality check event requirements.
        
        Returns:
            True if quality check event is valid, False otherwise
        """
        # Use parent validation first
        if not super().validate_domain_specific():
            return False
        
        # Check result is valid
        valid_results = ["passed", "failed", "pending", "requires_review"]
        if self.check_result not in valid_results:
            return False
        
        # Check type is specified
        if not self.check_type or not isinstance(self.check_type, str):
            return False
        
        return True


class StatusUpdateEvent(DomainEvent):
    """
    Event for status updates in business domains.
    
    This event type is used for tracking status changes
    of entities throughout their lifecycle.
    """
    
    def __init__(self, entity_id: str, old_status: str, new_status: str,
                 reason: Optional[str] = None, domain_type: str = "generic",
                 details: Optional[Dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize a status update event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            old_status: Previous status of the entity
            new_status: New status of the entity
            reason: Reason for the status change
            domain_type: Domain this event belongs to
            details: Additional event details
            timestamp: Event timestamp (defaults to current time)
        """
        self.old_status = old_status
        self.new_status = new_status
        self.reason = reason
        
        # Create event type
        event_type = "status_update"
        
        # Add status info to details
        status_details = details or {}
        status_details.update({
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "status_changed_at": timestamp or time.time()
        })
        
        super().__init__(entity_id, event_type, domain_type, status_details, timestamp)
    
    def validate_domain_specific(self) -> bool:
        """
        Validate status update event requirements.
        
        Returns:
            True if status update event is valid, False otherwise
        """
        # Use parent validation first
        if not super().validate_domain_specific():
            return False
        
        # Check statuses are specified
        if not self.old_status or not isinstance(self.old_status, str):
            return False
        
        if not self.new_status or not isinstance(self.new_status, str):
            return False
        
        # Statuses should be different
        if self.old_status == self.new_status:
            return False
        
        return True


class ApprovalEvent(DomainEvent):
    """
    Event for approval processes in business domains.
    
    This event type is used for tracking approvals, rejections,
    and authorization processes.
    """
    
    def __init__(self, entity_id: str, approval_type: str, approval_status: str,
                 approver_id: str, domain_type: str = "generic",
                 details: Optional[Dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize an approval event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            approval_type: Type of approval being processed
            approval_status: Status of the approval (approved, rejected, pending)
            approver_id: Identifier of the approver
            domain_type: Domain this event belongs to
            details: Additional event details
            timestamp: Event timestamp (defaults to current time)
        """
        self.approval_type = approval_type
        self.approval_status = approval_status
        self.approver_id = approver_id
        
        # Create event type
        event_type = "approval"
        
        # Add approval info to details
        approval_details = details or {}
        approval_details.update({
            "approval_type": approval_type,
            "approval_status": approval_status,
            "approver_id": approver_id,
            "approval_processed_at": timestamp or time.time()
        })
        
        super().__init__(entity_id, event_type, domain_type, approval_details, timestamp)
    
    def validate_domain_specific(self) -> bool:
        """
        Validate approval event requirements.
        
        Returns:
            True if approval event is valid, False otherwise
        """
        # Use parent validation first
        if not super().validate_domain_specific():
            return False
        
        # Check approval status is valid
        valid_statuses = ["approved", "rejected", "pending", "requires_review"]
        if self.approval_status not in valid_statuses:
            return False
        
        # Check approval type and approver are specified
        if not self.approval_type or not isinstance(self.approval_type, str):
            return False
        
        if not self.approver_id or not isinstance(self.approver_id, str):
            return False
        
        return True


class ComplianceEvent(DomainEvent):
    """
    Event for compliance tracking in business domains.
    
    This event type is used for tracking compliance checks,
    regulatory requirements, and audit trails.
    """
    
    def __init__(self, entity_id: str, compliance_type: str, compliance_status: str,
                 regulation_reference: Optional[str] = None, domain_type: str = "generic",
                 details: Optional[Dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize a compliance event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            compliance_type: Type of compliance being tracked
            compliance_status: Status of compliance (compliant, non_compliant, under_review)
            regulation_reference: Reference to specific regulation or standard
            domain_type: Domain this event belongs to
            details: Additional event details
            timestamp: Event timestamp (defaults to current time)
        """
        self.compliance_type = compliance_type
        self.compliance_status = compliance_status
        self.regulation_reference = regulation_reference
        
        # Create event type
        event_type = "compliance_check"
        
        # Add compliance info to details
        compliance_details = details or {}
        compliance_details.update({
            "compliance_type": compliance_type,
            "compliance_status": compliance_status,
            "regulation_reference": regulation_reference,
            "compliance_checked_at": timestamp or time.time()
        })
        
        super().__init__(entity_id, event_type, domain_type, compliance_details, timestamp)
    
    def validate_domain_specific(self) -> bool:
        """
        Validate compliance event requirements.
        
        Returns:
            True if compliance event is valid, False otherwise
        """
        # Use parent validation first
        if not super().validate_domain_specific():
            return False
        
        # Check compliance status is valid
        valid_statuses = ["compliant", "non_compliant", "under_review", "exempt"]
        if self.compliance_status not in valid_statuses:
            return False
        
        # Check compliance type is specified
        if not self.compliance_type or not isinstance(self.compliance_type, str):
            return False
        
        return True


class EventFactory:
    """
    Factory class for creating domain events.
    
    This factory provides a convenient way to create various types of
    domain events while ensuring proper structure and validation.
    """
    
    @staticmethod
    def create_resource_allocation(entity_id: str, resource_type: str, resource_id: str,
                                 allocation_type: str = "assigned", domain_type: str = "generic",
                                 **kwargs) -> ResourceAllocationEvent:
        """Create a resource allocation event."""
        return ResourceAllocationEvent(
            entity_id=entity_id,
            resource_type=resource_type,
            resource_id=resource_id,
            allocation_type=allocation_type,
            domain_type=domain_type,
            **kwargs
        )
    
    @staticmethod
    def create_quality_check(entity_id: str, check_type: str, check_result: str,
                           domain_type: str = "generic", **kwargs) -> QualityCheckEvent:
        """Create a quality check event."""
        return QualityCheckEvent(
            entity_id=entity_id,
            check_type=check_type,
            check_result=check_result,
            domain_type=domain_type,
            **kwargs
        )
    
    @staticmethod
    def create_status_update(entity_id: str, old_status: str, new_status: str,
                           domain_type: str = "generic", **kwargs) -> StatusUpdateEvent:
        """Create a status update event."""
        return StatusUpdateEvent(
            entity_id=entity_id,
            old_status=old_status,
            new_status=new_status,
            domain_type=domain_type,
            **kwargs
        )
    
    @staticmethod
    def create_approval(entity_id: str, approval_type: str, approval_status: str,
                       approver_id: str, domain_type: str = "generic", **kwargs) -> ApprovalEvent:
        """Create an approval event."""
        return ApprovalEvent(
            entity_id=entity_id,
            approval_type=approval_type,
            approval_status=approval_status,
            approver_id=approver_id,
            domain_type=domain_type,
            **kwargs
        )
    
    @staticmethod
    def create_compliance_check(entity_id: str, compliance_type: str, compliance_status: str,
                              domain_type: str = "generic", **kwargs) -> ComplianceEvent:
        """Create a compliance event."""
        return ComplianceEvent(
            entity_id=entity_id,
            compliance_type=compliance_type,
            compliance_status=compliance_status,
            domain_type=domain_type,
            **kwargs
        )