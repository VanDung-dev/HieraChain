"""
Domain Event implementations for HieraChain Ledger.

This module provides concrete domain-specific event implementations that extend
the base event classes for common business scenarios. These events follow
Ledger guidelines and can be used as templates for custom domain implementations.
"""

from typing import Any

from hierachain.domains.events.base_event import BaseEvent


class DomainEvent(BaseEvent):
    """
    Generic domain event that can be customized for specific business domains.
    
    This class provides a flexible foundation for domain-specific events
    while maintaining compliance with Ledger guidelines.
    """
    
    def __init__(
        self,
        entity_id: str,
        event_type: str,
        domain_type: str,
        details: dict[str, Any] | None = None,
        timestamp: float | None = None
    ):
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


# Import and expose sub-components for backward compatibility
from hierachain.domains.events.custom_events import (
    ResourceAllocationEvent,
    QualityCheckEvent,
    StatusUpdateEvent,
    ApprovalEvent,
    ComplianceEvent,
)

from hierachain.domains.events.event_creators import (
    create_resource_allocation,
    create_quality_check,
    create_status_update,
    create_approval,
    create_compliance_check,
)

__all__ = [
    "DomainEvent",
    "ResourceAllocationEvent",
    "QualityCheckEvent",
    "StatusUpdateEvent",
    "ApprovalEvent",
    "ComplianceEvent",
    "create_resource_allocation",
    "create_quality_check",
    "create_status_update",
    "create_approval",
    "create_compliance_check",
]

