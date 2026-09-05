"""
Base Event class for HieraChain Ledger.

This module defines the base event class that serves as the foundation
for all domain-specific events in the HieraChain Ledger.
It ensures proper event structure following Ledger guidelines.
"""

import time
from typing import Any
from abc import ABC, abstractmethod

from hierachain.core.utils import validate_event_structure


class BaseEvent(ABC):
    """
    Abstract base class for all events in the HieraChain Ledger.
    
    This class ensures that all events follow the Ledger guidelines:
    - Use entity_id as metadata field (not as block identifier)
    - Follow proper event structure with required fields
    - Avoid cryptocurrency terminology
    - Support domain-specific customization
    """
    
    def __init__(
        self,
        entity_id: str, event_type: str,
        details: dict[str, Any] | None = None,
        timestamp: float | None = None
    ):
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
        Validate the event structure according to Ledger guidelines.
        
        Raises:
            ValueError: If event structure is invalid
        """
        event_dict = self.to_dict()
        
        # Basic structure validation (includes crypto term check)
        if not validate_event_structure(event_dict):
            raise ValueError("Invalid event structure")
        
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
        raise NotImplementedError(
            "Subclasses must implement validate_domain_specific()"
        )
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert event to dictionary representation.
        
        Returns:
            Dictionary representation of the event following Ledger guidelines
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
        return (
            f"{self.__class__.__name__}(entity_id={self.entity_id}, "
            f"type={self.event_type})"
        )
    
    def __repr__(self) -> str:
        """Detailed string representation of the event."""
        return (f"{self.__class__.__name__}(entity_id={self.entity_id}, "
                f"event_type={self.event_type}, timestamp={self.timestamp}, "
                f"details_count={len(self.details)})")
    
    def __eq__(self, other: object) -> bool:
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



