"""
Base Chain class for HieraChain Ledger.

This module defines the base chain class that serves as the foundation
for domain-specific chain implementations. It extends the SubChain class
with domain-specific functionality while maintaining Ledger guidelines.
"""

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from hierachain.core.utils import get_block_events as _get_block_events
from hierachain.domains.events.base_event import BaseEvent
from hierachain.hierarchical.sub_chain import SubChain

logger = logging.getLogger(__name__)


class BaseChain(SubChain, ABC):
    """
    Abstract base class for domain-specific chains in the hierarchical Ledger.
    
    This class extends SubChain with domain-specific functionality:
    - Provides common domain operations
    - Handles domain-specific event creation and validation
    - Maintains entity lifecycle management
    - Supports domain-specific business rules
    """
    
    def __init__(self, name: str, domain_type: str) -> None:
        """
        Initialize a base domain chain.
        
        Args:
            name: Name identifier for the chain
            domain_type: Type of domain this chain handles
        """
        super().__init__(name, domain_type)
        self.entity_registry: dict[str, dict[str, Any]] = {}
        self.domain_rules: dict[str, Callable] = {}
        self.event_handlers: dict[str, Callable] = {}
        
        # Register default event handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default event handlers for common event types."""
        self.event_handlers.update({
            "operation_start": self._handle_operation_start,
            "operation_complete": self._handle_operation_complete,
            "status_update": self._handle_status_update,
            "resource_assigned": self._handle_resource_allocation,
            "resource_released": self._handle_resource_allocation,
            "resource_reserved": self._handle_resource_allocation,
            "resource_transferred": self._handle_resource_allocation,
            "quality_check": self._handle_quality_check,
            "approval": self._handle_approval,
            "compliance_check": self._handle_compliance_check
        })
    
    def register_entity(self, entity_id: str, entity_data: dict[str, Any]) -> bool:
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
        
        # Add registration metadata only after the event is accepted.
        registered_data = {
            **entity_data,
            "registered_at": time.time(),
            "registered_by": self.name,
            "domain_type": self.domain_type,
            "status": "registered",
        }
        
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
        
        try:
            if not self.add_event(registration_event):
                return False
        except Exception:
            logger.exception("Could not register entity %s", entity_id)
            return False
        self.entity_registry[entity_id] = registered_data
        return True
    
    def get_entity_info(self, entity_id: str) -> dict[str, Any] | None:
        """
        Get information about a registered entity.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            Entity information or None if not found
        """
        return self.entity_registry.get(entity_id)
    
    def get_entity_history(self, entity_id: str) -> list[dict[str, Any]]:
        """
        Get complete history of events for a specific entity.
        
        Args:
            entity_id: Entity identifier to search for
            
        Returns:
            List of events for the specified entity, ordered by timestamp
        """
        history = []
        for block in self.chain:
            events = _get_block_events(block)
            # Filter events for this entity
            entity_events = [e for e in events if e.get("entity_id") == entity_id]
            history.extend(entity_events)
            
        return history

    def add_domain_event(self, event: BaseEvent) -> bool:
        """
        Add a domain event to the chain with validation and processing.
        
        Args:
            event: Domain event to add
            
        Returns:
            True if event was added successfully, False otherwise
        """
        # Validate event
        if event.entity_id not in self.entity_registry or not event.is_valid():
            return False
        if event.event_type.startswith("resource_") and not self._can_apply_resource_allocation(event):
            return False
        
        # Convert to dictionary and add to chain
        event_dict = event.to_dict()
        try:
            if not self.add_event(event_dict):
                return False
        except Exception:
            logger.exception("Could not add domain event %s", event.event_type)
            return False
        
        # Process event with registered handlers
        event_type = event.event_type
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type](event)
            except Exception as e:
                logger.error("Error processing event %s: %s", event_type, e)
                return False
        
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
            self.entity_registry[entity_id]["last_operation_completed"] = (
                event.timestamp
            )
    
    def _handle_status_update(self, event: BaseEvent) -> None:
        """Handle status update events."""
        entity_id = event.entity_id
        new_status = event.get_detail("new_status")
        
        # Update entity status if registered
        if entity_id in self.entity_registry:
            self.entity_registry[entity_id]["status"] = new_status
            self.entity_registry[entity_id]["status_updated_at"] = event.timestamp
    
    def _ensure_resource_list(self, entity_id: str, field: str) -> list[str]:
        """Ensure the entity has the requested resource list."""
        return self.entity_registry[entity_id].setdefault(field, [])

    def _can_apply_resource_allocation(self, event: BaseEvent) -> bool:
        """Reject unsupported or impossible resource transitions before appending."""
        resource_id = event.get_detail("resource_id")
        resource_type = event.get_detail("resource_type")
        allocation_type = event.get_detail("allocation_type")
        if (
            not isinstance(resource_id, str) or not resource_id
            or not isinstance(resource_type, str) or not resource_type
            or event.event_type != f"resource_{allocation_type}"
        ):
            return False

        entity = self.entity_registry[event.entity_id]
        allocated = entity.get("allocated_resources", [])
        reserved = entity.get("reserved_resources", [])
        if not isinstance(allocated, list) or not isinstance(reserved, list):
            return False
        if allocation_type == "assigned":
            return resource_id not in allocated
        if allocation_type == "reserved":
            return resource_id not in allocated and resource_id not in reserved
        if allocation_type == "released":
            return resource_id in allocated or resource_id in reserved
        if allocation_type == "transferred":
            target_id = event.get_detail("target_entity_id")
            if not isinstance(target_id, str) or not target_id or target_id == event.entity_id:
                return False
            target = self.entity_registry.get(target_id)
            if target is None:
                return False
            target_allocated = target.get("allocated_resources", [])
            target_reserved = target.get("reserved_resources", [])
            return (
                resource_id in allocated
                and isinstance(target_allocated, list)
                and isinstance(target_reserved, list)
                and resource_id not in target_allocated
                and resource_id not in target_reserved
            )
        return False

    def _handle_resource_allocation(self, event: BaseEvent) -> None:
        """Handle resource allocation events."""
        entity_id = event.entity_id
        resource_id = event.get_detail("resource_id")
        allocation_type = event.get_detail("allocation_type")
        allocated = self._ensure_resource_list(entity_id, "allocated_resources")
        reserved = self._ensure_resource_list(entity_id, "reserved_resources")
        
        if allocation_type == "assigned":
            if resource_id in reserved:
                reserved.remove(resource_id)
            allocated.append(resource_id)
        elif allocation_type == "reserved":
            reserved.append(resource_id)
        elif allocation_type == "released":
            resources = allocated if resource_id in allocated else reserved
            resources.remove(resource_id)
        elif allocation_type == "transferred":
            allocated.remove(resource_id)
            target_id = event.get_detail("target_entity_id")
            self._ensure_resource_list(target_id, "allocated_resources").append(resource_id)
    
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
        for _, rule_function in self.domain_rules.items():
            try:
                if not rule_function(entity_info, operation):
                    return False
            except (ValueError, TypeError, AttributeError, KeyError):
                return False
        
        return True
    
    @abstractmethod
    def validate_domain_operation(
        self,
        entity_id: str,
        operation_type: str,
        operation_data: dict[str, Any]
    ) -> bool:
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
        raise NotImplementedError(
            "Subclasses must implement validate_domain_operation()"
        )
    
    @abstractmethod
    def get_domain_statistics(self) -> dict[str, Any]:
        """
        Get domain-specific statistics.
        
        This method should be implemented by specific domain chains
        to provide their own statistics.
        
        Returns:
            Domain-specific statistics
        """
        raise NotImplementedError("Subclasses must implement get_domain_statistics()")
    
    def get_base_domain_statistics(self) -> dict[str, Any]:
        """
        Get base domain statistics common to all domain chains.
        
        Returns:
            Base domain statistics
        """
        base_stats = super().get_domain_statistics()
        
        # Add domain-specific stats
        entity_statuses: dict[str, int] = {}
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
        return (
            f"{self.__class__.__name__}(name={self.name}, "
            f"domain={self.domain_type}, entities={len(self.entity_registry)})"
        )
    
    def __repr__(self) -> str:
        """Detailed string representation of the base chain."""
        return (
            f"{self.__class__.__name__}(name={self.name}, "
            f"domain_type={self.domain_type}, "
            f"entities={len(self.entity_registry)}, "
            f"blocks={len(self.chain)}, "
            f"operations={self.completed_operations})"
        )
