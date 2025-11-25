"""
Base Chain class for HieraChain Framework.

This module defines the base chain class that serves as the foundation
for domain-specific chain implementations. It extends the SubChain class
with domain-specific functionality while maintaining framework guidelines.
"""

import time
from typing import Dict, Any, Optional, Callable
from abc import ABC, abstractmethod

from hierachain.hierarchical.sub_chain import SubChain
from hierachain.domains.generic.events.base_event import BaseEvent


class BaseChain(SubChain, ABC):
    """
    Abstract base class for domain-specific chains in the hierarchical framework.
    
    This class extends SubChain with domain-specific functionality:
    - Provides common domain operations
    - Handles domain-specific event creation and validation
    - Maintains entity lifecycle management
    - Supports domain-specific business rules
    """
    
    def __init__(self, name: str, domain_type: str):
        """
        Initialize a base domain chain.
        
        Args:
            name: Name identifier for the chain
            domain_type: Type of domain this chain handles
        """
        super().__init__(name, domain_type)
        self.entity_registry: Dict[str, Dict[str, Any]] = {}
        self.domain_rules: Dict[str, Callable] = {}
        self.event_handlers: Dict[str, Callable] = {}
        
        # Register default event handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default event handlers for common event types."""
        self.event_handlers.update({
            "operation_start": self._handle_operation_start,
            "operation_complete": self._handle_operation_complete,
            "status_update": self._handle_status_update,
            "resource_assigned": self._handle_resource_allocation,
            "quality_check": self._handle_quality_check,
            "approval": self._handle_approval,
            "compliance_check": self._handle_compliance_check
        })
    
    def register_entity(self, entity_id: str, entity_data: Dict[str, Any]) -> bool:
        """
        Register a new entity in the domain chain.
        
        Args:
            entity_id: Unique identifier for the entity
            entity_data: Initial data for the entity
            
        Returns:
            True if entity was registered successfully, False otherwise
        """
        if entity_id in self.entity_registry:
            return False
        
        # Add registration metadata
        entity_data.update({
            "registered_at": time.time(),
            "registered_by": self.name,
            "domain_type": self.domain_type,
            "status": "registered"
        })
        
        self.entity_registry[entity_id] = entity_data
        
        # Create registration event
        registration_event = {
            "entity_id": entity_id,  # Metadata field
            "event": "entity_registration",
            "timestamp": time.time(),
            "details": {
                "domain_type": self.domain_type,
                "registered_by": self.name,
                "initial_status": "registered"
            }
        }
        
        self.add_event(registration_event)
        return True
    
    def get_entity_info(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a registered entity.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            Entity information or None if not found
        """
        return self.entity_registry.get(entity_id)
    
    def update_entity_info(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update information for a registered entity.
        
        Args:
            entity_id: Entity identifier
            updates: Updates to apply to entity data
            
        Returns:
            True if entity was updated successfully, False otherwise
        """
        if entity_id not in self.entity_registry:
            return False
        
        # Update entity data
        self.entity_registry[entity_id].update(updates)
        self.entity_registry[entity_id]["last_updated"] = time.time()
        
        # Create update event
        update_event = {
            "entity_id": entity_id,  # Metadata field
            "event": "entity_updated",
            "timestamp": time.time(),
            "details": {
                "updated_fields": list(updates.keys()),
                "updated_by": self.name,
                "domain_type": self.domain_type
            }
        }
        
        self.add_event(update_event)
        return True
    
    def create_domain_event(self, event_class: type, entity_id: str, **kwargs) -> BaseEvent:
        """
        Create a domain-specific event using the provided event class.
        
        Args:
            event_class: Event class to instantiate
            entity_id: Entity identifier (used as metadata)
            **kwargs: Additional arguments for event creation
            
        Returns:
            Created domain event
        """
        # Add domain type to kwargs
        kwargs.setdefault("domain_type", self.domain_type)
        
        # Create the event
        event = event_class(entity_id=entity_id, **kwargs)
        
        # Validate the event
        if not event.is_valid():
            raise ValueError(f"Invalid event created: {event}")
        
        return event
    
    def add_domain_event(self, event: BaseEvent) -> bool:
        """
        Add a domain event to the chain with validation and processing.
        
        Args:
            event: Domain event to add
            
        Returns:
            True if event was added successfully, False otherwise
        """
        # Validate event
        if not event.is_valid():
            return False
        
        # Convert to dictionary and add to chain
        event_dict = event.to_dict()
        self.add_event(event_dict)
        
        # Process event with registered handlers
        event_type = event.event_type
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type](event)
            except Exception as e:
                # Log error but don't fail the event addition
                print(f"Error processing event {event_type}: {e}")
        
        return True
    
    def _handle_operation_start(self, event: BaseEvent) -> None:
        """Handle operation start events."""
        entity_id = event.entity_id
        operation_type = event.get_detail("operation_type")
        
        # Update entity status if registered
        if entity_id in self.entity_registry:
            self.entity_registry[entity_id]["current_operation"] = operation_type
            self.entity_registry[entity_id]["operation_started_at"] = event.timestamp
    
    def _handle_operation_complete(self, event: BaseEvent) -> None:
        """Handle operation complete events."""
        entity_id = event.entity_id
        
        # Update entity status if registered
        if entity_id in self.entity_registry:
            self.entity_registry[entity_id].pop("current_operation", None)
            self.entity_registry[entity_id]["last_operation_completed"] = event.timestamp
    
    def _handle_status_update(self, event: BaseEvent) -> None:
        """Handle status update events."""
        entity_id = event.entity_id
        new_status = event.get_detail("new_status")
        
        # Update entity status if registered
        if entity_id in self.entity_registry:
            self.entity_registry[entity_id]["status"] = new_status
            self.entity_registry[entity_id]["status_updated_at"] = event.timestamp
    
    def _handle_resource_allocation(self, event: BaseEvent) -> None:
        """Handle resource allocation events."""
        entity_id = event.entity_id
        resource_id = event.get_detail("resource_id")
        allocation_type = event.get_detail("allocation_type")
        
        # Update entity resources if registered
        if entity_id in self.entity_registry:
            if "allocated_resources" not in self.entity_registry[entity_id]:
                self.entity_registry[entity_id]["allocated_resources"] = []
            
            if allocation_type == "assigned":
                self.entity_registry[entity_id]["allocated_resources"].append(resource_id)
            elif allocation_type == "released":
                if resource_id in self.entity_registry[entity_id]["allocated_resources"]:
                    self.entity_registry[entity_id]["allocated_resources"].remove(resource_id)
    
    def _handle_quality_check(self, event: BaseEvent) -> None:
        """Handle quality check events."""
        entity_id = event.entity_id
        check_result = event.get_detail("check_result")
        
        # Update entity quality status if registered
        if entity_id in self.entity_registry:
            self.entity_registry[entity_id]["last_quality_check"] = {
                "result": check_result,
                "timestamp": event.timestamp
            }
    
    def _handle_approval(self, event: BaseEvent) -> None:
        """Handle approval events."""
        entity_id = event.entity_id
        approval_status = event.get_detail("approval_status")
        approval_type = event.get_detail("approval_type")
        
        # Update entity approval status if registered
        if entity_id in self.entity_registry:
            if "approvals" not in self.entity_registry[entity_id]:
                self.entity_registry[entity_id]["approvals"] = {}
            
            self.entity_registry[entity_id]["approvals"][approval_type] = {
                "status": approval_status,
                "timestamp": event.timestamp
            }
    
    def _handle_compliance_check(self, event: BaseEvent) -> None:
        """Handle compliance check events."""
        entity_id = event.entity_id
        compliance_status = event.get_detail("compliance_status")
        compliance_type = event.get_detail("compliance_type")
        
        # Update entity compliance status if registered
        if entity_id in self.entity_registry:
            if "compliance" not in self.entity_registry[entity_id]:
                self.entity_registry[entity_id]["compliance"] = {}
            
            self.entity_registry[entity_id]["compliance"][compliance_type] = {
                "status": compliance_status,
                "timestamp": event.timestamp
            }
    
    def add_domain_rule(self, rule_name: str, rule_function: Callable) -> None:
        """
        Add a domain-specific business rule.
        
        Args:
            rule_name: Name of the rule
            rule_function: Function that implements the rule
        """
        self.domain_rules[rule_name] = rule_function
    
    def validate_domain_rules(self, entity_id: str, operation: str) -> bool:
        """
        Validate domain rules for an entity and operation.
        
        Args:
            entity_id: Entity identifier
            operation: Operation being performed
            
        Returns:
            True if all domain rules pass, False otherwise
        """
        entity_info = self.get_entity_info(entity_id)
        if not entity_info:
            return False
        
        # Apply all domain rules
        for rule_name, rule_function in self.domain_rules.items():
            try:
                if not rule_function(entity_info, operation):
                    return False
            except (ValueError, TypeError, AttributeError, KeyError):
                return False
        
        return True
    
    def get_entity_lifecycle_summary(self, entity_id: str) -> Dict[str, Any]:
        """
        Get a summary of an entity's lifecycle in this domain.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            Lifecycle summary for the entity
        """
        entity_info = self.get_entity_info(entity_id)
        if not entity_info:
            return {}
        
        # Get all events for this entity
        entity_events = self.get_entity_history(entity_id)
        
        # Analyze lifecycle
        lifecycle_summary = {
            "entity_id": entity_id,
            "domain_type": self.domain_type,
            "registered_at": entity_info.get("registered_at"),
            "current_status": entity_info.get("status"),
            "total_events": len(entity_events),
            "event_types": list(set(event.get("event") for event in entity_events)),
            "last_activity": max((event.get("timestamp", 0) for event in entity_events), default=0),
            "allocated_resources": entity_info.get("allocated_resources", []),
            "current_operation": entity_info.get("current_operation"),
            "approvals": entity_info.get("approvals", {}),
            "compliance": entity_info.get("compliance", {})
        }
        
        return lifecycle_summary
    
    @abstractmethod
    def validate_domain_operation(self, entity_id: str, operation_type: str, 
                                 operation_data: Dict[str, Any]) -> bool:
        """
        Validate a domain-specific operation.
        
        This method should be implemented by specific domain chains
        to add their own operation validation logic.
        
        Args:
            entity_id: Entity identifier
            operation_type: Type of operation
            operation_data: Operation data
            
        Returns:
            True if operation is valid for this domain, False otherwise
        """
        pass
    
    @abstractmethod
    def get_domain_statistics(self) -> Dict[str, Any]:
        """
        Get domain-specific statistics.
        
        This method should be implemented by specific domain chains
        to provide their own statistics.
        
        Returns:
            Domain-specific statistics
        """
        pass
    
    def get_base_domain_statistics(self) -> Dict[str, Any]:
        """
        Get base domain statistics common to all domain chains.
        
        Returns:
            Base domain statistics
        """
        base_stats = super().get_domain_statistics()
        
        # Add domain-specific stats
        entity_statuses = {}
        for entity_info in self.entity_registry.values():
            status = entity_info.get("status", "unknown")
            entity_statuses[status] = entity_statuses.get(status, 0) + 1
        
        base_stats.update({
            "registered_entities": len(self.entity_registry),
            "entity_statuses": entity_statuses,
            "domain_rules": len(self.domain_rules),
            "event_handlers": len(self.event_handlers)
        })
        
        return base_stats
    
    def __str__(self) -> str:
        """String representation of the base chain."""
        return f"{self.__class__.__name__}(name={self.name}, domain={self.domain_type}, entities={len(self.entity_registry)})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the base chain."""
        return (f"{self.__class__.__name__}(name={self.name}, domain_type={self.domain_type}, "
                f"entities={len(self.entity_registry)}, blocks={len(self.chain)}, "
                f"operations={self.completed_operations})")