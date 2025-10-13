"""
Enhanced Domain Contract System for Hierarchical Blockchain Framework.

This module implements an advanced domain-specific contract system with versioning,
lifecycle management, and event handlers. The system enables business logic evolution
without disrupting ongoing operations while ensuring real-time monitoring of compliance
and security controls across enterprise processes.
"""

import time
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum


class ContractStatus(Enum):
    """Contract lifecycle status"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class ContractEventType(Enum):
    """Contract event types"""
    DEPLOYED = "deployed"
    ACTIVATED = "activated"
    EXECUTED = "executed"
    UPGRADED = "upgraded"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class ContractVersion:
    """Contract version information"""
    major: int
    minor: int
    patch: int
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __lt__(self, other: 'ContractVersion') -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __le__(self, other: 'ContractVersion') -> bool:
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)
    
    def __gt__(self, other: 'ContractVersion') -> bool:
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)
    
    def __ge__(self, other: 'ContractVersion') -> bool:
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)
    
    def __eq__(self, other: 'ContractVersion') -> bool:
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
    
    @classmethod
    def from_string(cls, version_str: str) -> 'ContractVersion':
        """Create version from string like '1.2.3'"""
        parts = version_str.split('.')
        if len(parts) != 3:
            raise ValueError("Version must be in format 'major.minor.patch'")
        return cls(int(parts[0]), int(parts[1]), int(parts[2]))


class ContractStorage:
    """Contract storage with persistence capabilities"""
    
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.event_log: List[Dict[str, Any]] = []
        
    def set(self, key: str, value: Any, contract_id: str = None) -> None:
        """Set a value in contract storage"""
        old_value = self.data.get(key)
        self.data[key] = value
        
        # Log the event
        self.event_log.append({
            "timestamp": time.time(),
            "operation": "set",
            "key": key,
            "old_value": old_value,
            "new_value": value,
            "contract_id": contract_id
        })
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from contract storage"""
        return self.data.get(key, default)
    
    def delete(self, key: str, contract_id: str = None) -> bool:
        """Delete a key from contract storage"""
        if key in self.data:
            old_value = self.data.pop(key)
            
            # Log the event
            self.event_log.append({
                "timestamp": time.time(),
                "operation": "delete",
                "key": key,
                "old_value": old_value,
                "contract_id": contract_id
            })
            return True
        return False
    
    def keys(self) -> List[str]:
        """Get all keys in storage"""
        return list(self.data.keys())
    
    def get_event_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent event log entries"""
        return self.event_log[-limit:] if limit > 0 else self.event_log
    
    def clear(self, contract_id: str = None) -> None:
        """Clear all data from storage"""
        self.data.clear()
        self.event_log.append({
            "timestamp": time.time(),
            "operation": "clear",
            "contract_id": contract_id
        })


class ContractLifecycle:
    """Contract lifecycle management"""
    
    def __init__(self):
        self.status = ContractStatus.DEVELOPMENT
        self.status_history: List[Dict[str, Any]] = []
        self.deployment_info: Optional[Dict[str, Any]] = None
        self.deprecation_info: Optional[Dict[str, Any]] = None
        
    def transition_to(self, new_status: ContractStatus, reason: str = "", 
                     metadata: Dict[str, Any] = None) -> bool:
        """
        Transition contract to new status.
        
        Args:
            new_status: New contract status
            reason: Reason for status change
            metadata: Additional metadata for the transition
            
        Returns:
            True if transition was successful
        """
        # Validate transition
        if not self._is_valid_transition(self.status, new_status):
            return False
        
        # Record status change
        status_change = {
            "timestamp": time.time(),
            "from_status": self.status.value,
            "to_status": new_status.value,
            "reason": reason,
            "metadata": metadata or {}
        }
        
        self.status_history.append(status_change)
        self.status = new_status
        
        # Handle special status changes
        if new_status == ContractStatus.ACTIVE and not self.deployment_info:
            self.deployment_info = {
                "deployed_at": time.time(),
                "deployed_by": metadata.get("deployed_by", "system"),
                "deployment_metadata": metadata
            }
        elif new_status == ContractStatus.DEPRECATED and not self.deprecation_info:
            self.deprecation_info = {
                "deprecated_at": time.time(),
                "deprecated_by": metadata.get("deprecated_by", "system"),
                "deprecation_reason": reason,
                "end_of_life_date": metadata.get("end_of_life_date")
            }
        
        return True
    
    @staticmethod
    def _is_valid_transition(from_status: ContractStatus,
                             to_status: ContractStatus) -> bool:
        """Check if status transition is valid"""
        valid_transitions = {
            ContractStatus.DEVELOPMENT: [ContractStatus.TESTING, ContractStatus.DISABLED],
            ContractStatus.TESTING: [ContractStatus.ACTIVE, ContractStatus.DEVELOPMENT, ContractStatus.DISABLED],
            ContractStatus.ACTIVE: [ContractStatus.DEPRECATED, ContractStatus.DISABLED],
            ContractStatus.DEPRECATED: [ContractStatus.DISABLED, ContractStatus.ARCHIVED],
            ContractStatus.DISABLED: [ContractStatus.DEVELOPMENT, ContractStatus.ARCHIVED],
            ContractStatus.ARCHIVED: []  # No transitions from archived
        }
        
        return to_status in valid_transitions.get(from_status, [])
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get comprehensive status information"""
        return {
            "current_status": self.status.value,
            "status_history": self.status_history,
            "deployment_info": self.deployment_info,
            "deprecation_info": self.deprecation_info
        }


class DomainContract:
    """
    Advanced domain-specific contract system with versioning and lifecycle management.
    
    This class provides comprehensive contract management including versioning,
    lifecycle management, event handlers, and persistent storage for enterprise
    blockchain applications.
    """
    
    def __init__(self, contract_id: str, version: Union[str, ContractVersion], 
                 implementation: Optional[Callable] = None, 
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize domain contract.
        
        Args:
            contract_id: Unique contract identifier
            version: Semantic version of the contract
            implementation: Contract logic implementation (optional)
            metadata: Contract governance and configuration metadata
        """
        self.contract_id = contract_id
        self.version = version if isinstance(version, ContractVersion) else ContractVersion.from_string(version)
        self.implementation = implementation
        self.metadata = metadata or {}
        
        # Core components
        self.lifecycle = ContractLifecycle()
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.storage = ContractStorage()
        
        # Execution tracking
        self.execution_count = 0
        self.last_execution = None
        self.execution_history: List[Dict[str, Any]] = []
        self.error_count = 0
        self.last_error = None
        
        # Version management
        self.previous_versions: List['DomainContract'] = []
        self.deprecation_warning_days = metadata.get("deprecation_warning", 90)
        
        # Contract creation timestamp
        self.created_at = time.time()
        
        # Initialize default event handlers
        self._setup_default_handlers()
    
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        Register handler for specific domain events.
        
        Args:
            event_type: Type of event to handle
            handler: Handler function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        
        self._log_contract_event(ContractEventType.DEPLOYED, {
            "action": "handler_registered",
            "event_type": event_type,
            "handler": handler.__name__ if hasattr(handler, '__name__') else str(handler)
        })
    
    def unregister_event_handler(self, event_type: str, handler: Callable) -> bool:
        """
        Unregister a specific event handler.
        
        Args:
            event_type: Type of event
            handler: Handler to remove
            
        Returns:
            True if handler was removed
        """
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False
    
    def execute(self, event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute contract logic based on domain event.
        
        Args:
            event: Domain event to process
            context: Execution context
            
        Returns:
            Execution result with status and data
        """
        # Check if contract is active
        if self.lifecycle.status != ContractStatus.ACTIVE:
            return {
                "success": False,
                "error": f"Contract is not active (status: {self.lifecycle.status.value})",
                "contract_id": self.contract_id,
                "version": str(self.version)
            }
        
        execution_start = time.time()
        execution_result = {
            "success": False,
            "contract_id": self.contract_id,
            "version": str(self.version),
            "execution_time": 0,
            "event_type": event.get("event", "unknown"),
            "timestamp": execution_start
        }
        
        try:
            # Validate event
            if not self._validate_event(event):
                raise ValueError("Invalid event structure")
            
            # Execute main implementation if available
            if self.implementation:
                result = self.implementation(event, context or {}, self.storage)
                execution_result["result"] = result
            
            # Execute registered event handlers
            event_type = event.get("event", "unknown")
            if event_type in self.event_handlers:
                handler_results = []
                for handler in self.event_handlers[event_type]:
                    try:
                        handler_result = handler(event, context or {}, self.storage)
                        handler_results.append({
                            "handler": handler.__name__ if hasattr(handler, '__name__') else str(handler),
                            "result": handler_result,
                            "success": True
                        })
                    except Exception as handler_error:
                        handler_results.append({
                            "handler": handler.__name__ if hasattr(handler, '__name__') else str(handler),
                            "error": str(handler_error),
                            "success": False
                        })
                
                execution_result["handler_results"] = handler_results
            
            # Mark as successful
            execution_result["success"] = True
            
            # Update execution tracking
            self.execution_count += 1
            self.last_execution = execution_start
            
            # Log successful execution
            self._log_contract_event(ContractEventType.EXECUTED, {
                "event_type": event_type,
                "execution_time": time.time() - execution_start,
                "handlers_executed": len(self.event_handlers.get(event_type, []))
            })
            
        except Exception as e:
            # Handle execution error
            execution_result["error"] = str(e)
            self.error_count += 1
            self.last_error = {
                "timestamp": time.time(),
                "error": str(e),
                "event": event
            }
            
            # Log error
            self._log_contract_event(ContractEventType.ERROR, {
                "error": str(e),
                "event_type": event.get("event", "unknown")
            })
        
        # Calculate execution time
        execution_result["execution_time"] = time.time() - execution_start
        
        # Store in execution history
        self.execution_history.append(execution_result.copy())
        
        return execution_result
    
    def upgrade_to_version(self, new_version: Union[str, ContractVersion], 
                          new_implementation: Optional[Callable] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Upgrade contract to new version.
        
        Args:
            new_version: New version number
            new_implementation: New implementation (optional)
            metadata: Upgrade metadata
            
        Returns:
            True if upgrade was successful
        """
        new_version_obj = new_version if isinstance(new_version, ContractVersion) else ContractVersion.from_string(new_version)
        
        # Validate version is newer
        if new_version_obj <= self.version:
            return False
        
        # Store current version as previous
        current_contract = DomainContract(
            contract_id=self.contract_id,
            version=self.version,
            implementation=self.implementation,
            metadata=self.metadata.copy()
        )
        current_contract.lifecycle = self.lifecycle
        current_contract.execution_history = self.execution_history.copy()
        
        self.previous_versions.append(current_contract)
        
        # Limit version history
        max_versions = self.metadata.get("max_version_history", 10)
        if len(self.previous_versions) > max_versions:
            self.previous_versions = self.previous_versions[-max_versions:]
        
        # Update to new version
        self.version = new_version_obj
        if new_implementation:
            self.implementation = new_implementation
        
        if metadata:
            self.metadata.update(metadata)
        
        # Reset execution tracking for new version
        self.execution_count = 0
        self.last_execution = None
        self.execution_history = []
        self.error_count = 0
        self.last_error = None
        
        # Log upgrade
        self._log_contract_event(ContractEventType.UPGRADED, {
            "from_version": str(current_contract.version),
            "to_version": str(self.version),
            "upgrade_metadata": metadata or {}
        })
        
        return True
    
    def deprecate(self, reason: str = "", end_of_life_date: Optional[float] = None) -> bool:
        """
        Mark contract as deprecated.
        
        Args:
            reason: Deprecation reason
            end_of_life_date: When contract will be archived
            
        Returns:
            True if successfully deprecated
        """
        metadata = {"reason": reason}
        if end_of_life_date:
            metadata["end_of_life_date"] = end_of_life_date
        
        success = self.lifecycle.transition_to(ContractStatus.DEPRECATED, reason, metadata)
        
        if success:
            self._log_contract_event(ContractEventType.DEPRECATED, {
                "reason": reason,
                "end_of_life_date": end_of_life_date
            })
        
        return success
    
    def activate(self, deployed_by: str = "system") -> bool:
        """Activate the contract for production use"""
        metadata = {"deployed_by": deployed_by}
        success = self.lifecycle.transition_to(ContractStatus.ACTIVE, "Contract activated", metadata)
        
        if success:
            self._log_contract_event(ContractEventType.ACTIVATED, {
                "deployed_by": deployed_by,
                "activated_at": time.time()
            })
        
        return success
    
    def disable(self, reason: str = "Administrative action") -> bool:
        """Disable the contract"""
        success = self.lifecycle.transition_to(ContractStatus.DISABLED, reason)
        
        if success:
            self._log_contract_event(ContractEventType.DISABLED, {
                "reason": reason,
                "disabled_at": time.time()
            })
        
        return success
    
    def get_contract_info(self) -> Dict[str, Any]:
        """Get comprehensive contract information"""
        return {
            "contract_id": self.contract_id,
            "version": str(self.version),
            "status": self.lifecycle.status.value,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "execution_stats": {
                "execution_count": self.execution_count,
                "last_execution": self.last_execution,
                "error_count": self.error_count,
                "last_error": self.last_error
            },
            "lifecycle_info": self.lifecycle.get_status_info(),
            "event_handlers": {
                event_type: len(handlers) 
                for event_type, handlers in self.event_handlers.items()
            },
            "version_history": [str(v.version) for v in self.previous_versions],
            "storage_keys": len(self.storage.keys())
        }
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution history"""
        return self.execution_history[-limit:] if limit > 0 else self.execution_history
    
    @staticmethod
    def _validate_event(event: Dict[str, Any]) -> bool:
        """Validate event structure"""
        required_fields = ["entity_id", "event", "timestamp"]
        for field in required_fields:
            if field not in event:
                return False
        
        # Additional validation
        if not isinstance(event["timestamp"], (int, float)):
            return False
            
        if not isinstance(event["entity_id"], str) or len(event["entity_id"].strip()) == 0:
            return False
            
        if not isinstance(event["event"], str) or len(event["event"].strip()) == 0:
            return False
        
        return True
    
    def _setup_default_handlers(self) -> None:
        """Setup default event handlers"""
        def default_logging_handler(event: Dict[str, Any], context: Dict[str, Any], storage: ContractStorage):
            """Default handler that logs all events"""
            log_entry = {
                "timestamp": time.time(),
                "event_type": event.get("event"),
                "entity_id": event.get("entity_id"),
                "contract_id": self.contract_id,
                "version": str(self.version)
            }
            
            # Store in contract storage
            log_key = f"event_log:{time.time()}:{event.get('entity_id', 'unknown')}"
            storage.set(log_key, log_entry, self.contract_id)
        
        # Register default handler for all event types if no specific handlers exist
        self.default_handler = default_logging_handler
    
    def _log_contract_event(self, event_type: ContractEventType, details: Dict[str, Any]) -> None:
        """Log contract lifecycle events"""
        log_entry = {
            "timestamp": time.time(),
            "contract_id": self.contract_id,
            "version": str(self.version),
            "event_type": event_type.value,
            "details": details
        }
        
        # Store in contract storage
        log_key = f"contract_log:{time.time()}:{event_type.value}"
        self.storage.set(log_key, log_entry, self.contract_id)
    
    def __str__(self) -> str:
        """String representation of contract"""
        return f"DomainContract(id={self.contract_id}, version={self.version}, status={self.lifecycle.status.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"DomainContract(contract_id='{self.contract_id}', "
                f"version='{self.version}', status='{self.lifecycle.status.value}', "
                f"handlers={len(self.event_handlers)}, executions={self.execution_count})")