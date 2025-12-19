"""
Base Event class for HieraChain Framework.

This module defines the base event class that serves as the foundation
for all domain-specific events in the HieraChain framework.
It ensures proper event structure following framework guidelines.
"""

import time
from typing import Any, Optional
from abc import ABC, abstractmethod

from hierachain.core.utils import validate_event_structure, validate_no_cryptocurrency_terms


class BaseEvent(ABC):
    """
    Abstract base class for all events in the HieraChain framework.
    
    This class ensures that all events follow the framework guidelines:
    - Use entity_id as metadata field (not as block identifier)
    - Follow proper event structure with required fields
    - Avoid cryptocurrency terminology
    - Support domain-specific customization
    """
    
    def __init__(self, entity_id: str, event_type: str, 
                 details: Optional[dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize a base event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            event_type: Type of event
            details: Additional event details
            timestamp: Event timestamp (defaults to current time)
        """
        self.entity_id = entity_id  # Metadata field, not block identifier
        self.event_type = event_type
        self.details = details or {}
        self.timestamp = timestamp or time.time()
        
        # Validate the event structure
        self._validate_event()
    
    def _validate_event(self) -> None:
        """
        Validate the event structure according to framework guidelines.
        
        Raises:
            ValueError: If event structure is invalid
        """
        event_dict = self.to_dict()
        
        # Basic structure validation
        if not validate_event_structure(event_dict):
            raise ValueError("Invalid event structure")
        
        # Check for cryptocurrency terms
        if not validate_no_cryptocurrency_terms(event_dict):
            raise ValueError("Event contains forbidden cryptocurrency terminology")
        
        # Validate entity_id is used as metadata
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise ValueError("entity_id must be a non-empty string (metadata field)")
        
        # Validate event type
        if not isinstance(self.event_type, str) or not self.event_type:
            raise ValueError("event_type must be a non-empty string")
    
    @abstractmethod
    def validate_domain_specific(self) -> bool:
        """
        Validate domain-specific event requirements.
        
        This method should be implemented by domain-specific event classes
        to add their own validation logic.
        
        Returns:
            True if domain-specific validation passes, False otherwise
        """
        raise NotImplementedError("Subclasses must implement validate_domain_specific()")
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert event to dictionary representation.
        
        Returns:
            Dictionary representation of the event following framework guidelines
        """
        return {
            "entity_id": self.entity_id,  # Metadata field
            "event": self.event_type,
            "timestamp": self.timestamp,
            "details": self.details
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseEvent':
        """
        Create an event instance from dictionary data.
        
        Args:
            data: Dictionary containing event data
            
        Returns:
            Event instance
        """
        return cls(
            entity_id=data["entity_id"],
            event_type=data["event"],
            details=data.get("details", {}),
            timestamp=data.get("timestamp")
        )
    
    def add_detail(self, key: str, value: Any) -> None:
        """
        Add a detail to the event.
        
        Args:
            key: Detail key
            value: Detail value
        """
        self.details[key] = value
    
    def get_detail(self, key: str, default: Any = None) -> Any:
        """
        Get a detail from the event.
        
        Args:
            key: Detail key
            default: Default value if key not found
            
        Returns:
            Detail value or default
        """
        return self.details.get(key, default)
    
    def update_details(self, new_details: dict[str, Any]) -> None:
        """
        Update event details.
        
        Args:
            new_details: New details to merge with existing details
        """
        self.details.update(new_details)
    
    def is_valid(self) -> bool:
        """
        Check if the event is valid according to all validation rules.
        
        Returns:
            True if event is valid, False otherwise
        """
        try:
            self._validate_event()
            return self.validate_domain_specific()
        except ValueError:
            return False
    
    def get_event_summary(self) -> dict[str, Any]:
        """
        Get a summary of the event (suitable for Main Chain metadata).
        
        Returns:
            Summary dictionary with key event information
        """
        return {
            "event_type": self.event_type,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp,
            "has_details": len(self.details) > 0
        }
    
    def __str__(self) -> str:
        """String representation of the event."""
        return f"{self.__class__.__name__}(entity_id={self.entity_id}, type={self.event_type})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the event."""
        return (f"{self.__class__.__name__}(entity_id={self.entity_id}, "
                f"event_type={self.event_type}, timestamp={self.timestamp}, "
                f"details_count={len(self.details)})")
    
    def __eq__(self, other) -> bool:
        """Check equality with another event."""
        if not isinstance(other, BaseEvent):
            return False
        
        return (self.entity_id == other.entity_id and
                self.event_type == other.event_type and
                self.timestamp == other.timestamp and
                self.details == other.details)
    
    def __hash__(self) -> int:
        """Generate hash for the event."""
        return hash((self.entity_id, self.event_type, self.timestamp, 
                    tuple(sorted(self.details.items()))))


class GenericEvent(BaseEvent):
    """
    Generic event implementation for basic use cases.
    
    This class provides a concrete implementation of BaseEvent that can be
    used directly or as a reference for creating domain-specific events.
    """
    
    def __init__(self, entity_id: str, event_type: str, 
                 details: Optional[dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize a generic event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            event_type: Type of event
            details: Additional event details
            timestamp: Event timestamp (defaults to current time)
        """
        super().__init__(entity_id, event_type, details, timestamp)
    
    def validate_domain_specific(self) -> bool:
        """
        Validate generic event (always valid for basic events).
        
        Returns:
            True (generic events have no additional validation requirements)
        """
        return True


class OperationEvent(BaseEvent):
    """
    Operation-specific event for business operations.
    
    This class represents events related to business operations and includes
    additional validation for operation-specific requirements.
    """
    
    def __init__(self, entity_id: str, operation_type: str, 
                 operation_status: str = "started",
                 details: Optional[dict[str, Any]] = None, 
                 timestamp: Optional[float] = None):
        """
        Initialize an operation event.
        
        Args:
            entity_id: Entity identifier (used as metadata field)
            operation_type: Type of operation
            operation_status: Status of the operation (started, completed, failed)
            details: Additional operation details
            timestamp: Event timestamp (defaults to current time)
        """
        self.operation_type = operation_type
        self.operation_status = operation_status
        
        # Create event type from operation info
        event_type = f"operation_{operation_status}"
        
        # Add operation info to details
        operation_details = details or {}
        operation_details.update({
            "operation_type": operation_type,
            "operation_status": operation_status
        })
        
        super().__init__(entity_id, event_type, operation_details, timestamp)
    
    def validate_domain_specific(self) -> bool:
        """
        Validate operation-specific requirements.
        
        Returns:
            True if operation event is valid, False otherwise
        """
        # Check operation status is valid
        valid_statuses = ["started", "completed", "failed", "paused", "resumed"]
        if self.operation_status not in valid_statuses:
            return False
        
        # Check operation type is specified
        if not self.operation_type or not isinstance(self.operation_type, str):
            return False
        
        return True
    
    def complete_operation(self, result: Optional[dict[str, Any]] = None) -> 'OperationEvent':
        """
        Create a completion event for this operation.
        
        Args:
            result: Operation result data
            
        Returns:
            New OperationEvent with completed status
        """
        completion_details = self.details.copy()
        if result:
            completion_details["result"] = result
        completion_details["completed_at"] = time.time()
        
        return OperationEvent(
            entity_id=self.entity_id,
            operation_type=self.operation_type,
            operation_status="completed",
            details=completion_details
        )