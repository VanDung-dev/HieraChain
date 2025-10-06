"""
Enhanced ERP Integration Framework for Hierarchical Blockchain Framework

This module provides comprehensive ERP integration capabilities with advanced
mapping engine, event translation, change detection, and scheduled synchronization.
Supports SAP, Oracle, Microsoft Dynamics, and other enterprise systems.
"""

import time
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor


class IntegrationError(Exception):
    """Exception raised for integration-related errors"""
    pass


class MappingError(Exception):
    """Exception raised for mapping-related errors"""
    pass


class SyncStatus(Enum):
    """Synchronization status"""
    IDLE = "idle"
    SYNCING = "syncing"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class SyncResult:
    """Result of a synchronization operation"""
    profile_name: str
    status: SyncStatus
    events_processed: int
    errors: List[str] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def duration(self) -> float:
        """Get sync duration in seconds"""
        return self.end_time - self.start_time if self.end_time > 0 else 0.0


class ERPIntegrationFramework:
    """Comprehensive ERP integration framework with mapping engine"""
    
    def __init__(self):
        self.adapters: Dict[str, Any] = {}
        self.mapping_engine = MappingEngine()
        self.event_translator = EventTranslator()
        self.change_detector = ChangeDetector()
        self.sync_scheduler = SyncScheduler()
        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()
        
        # Register built-in transformers
        self._register_built_in_transformers()
    
    def _register_built_in_transformers(self):
        """Register built-in field transformers"""
        transformers = {
            "date": self._transform_date,
            "amount": self._transform_amount,
            "id": self._transform_id,
            "status": self._transform_status,
            "currency": self._transform_currency,
            "boolean": self._transform_boolean
        }
        
        for name, func in transformers.items():
            self.mapping_engine.register_transformer(name, func)
    
    def register_adapter(self, erp_system: str, adapter_class: Any):
        """Register ERP adapter"""
        with self.lock:
            self.adapters[erp_system] = adapter_class
            self.logger.info(f"Registered adapter for {erp_system}")
    
    def create_mapping_profile(self, profile_name: str, erp_system: str, 
                             mapping_rules: Dict[str, Any]) -> str:
        """Create mapping profile for ERP integration"""
        try:
            return self.mapping_engine.create_profile(
                profile_name, 
                erp_system,
                mapping_rules
            )
        except Exception as e:
            self.logger.error(f"Failed to create mapping profile {profile_name}: {e}")
            raise IntegrationError(f"Profile creation failed: {e}")
    
    def translate_erp_to_blockchain(self, erp_event: Dict[str, Any], 
                                  profile_name: str) -> Dict[str, Any]:
        """Translate ERP event to blockchain event"""
        try:
            # Get mapping profile
            profile = self.mapping_engine.get_profile(profile_name)
            if not profile:
                raise IntegrationError(f"Mapping profile {profile_name} not found")
            
            # Detect changes if needed
            if profile.get("detect_changes", False):
                erp_event = self.change_detector.detect_changes(erp_event, profile)
            
            # Translate using mapping rules
            blockchain_event = self.event_translator.translate(
                erp_event, 
                profile["mapping_rules"]
            )
            
            return blockchain_event
            
        except Exception as e:
            self.logger.error(f"Translation failed for profile {profile_name}: {e}")
            raise IntegrationError(f"Translation failed: {e}")
    
    def start_scheduled_sync(self, profile_name: str, interval_seconds: int,
                           chain: Any = None) -> str:
        """Start scheduled synchronization"""
        try:
            profile = self.mapping_engine.get_profile(profile_name)
            if not profile:
                raise IntegrationError(f"Mapping profile {profile_name} not found")
            
            # Get adapter
            adapter_class = self.adapters.get(profile["erp_system"])
            if not adapter_class:
                raise IntegrationError(f"No adapter for {profile['erp_system']}")
            
            adapter = adapter_class(profile.get("config", {}))
            
            def sync_task():
                return self._execute_sync(profile_name, profile, adapter, chain)
            
            # Schedule the task
            task_id = self.sync_scheduler.schedule_task(
                profile_name,
                sync_task,
                interval_seconds
            )
            
            self.logger.info(f"Scheduled sync for {profile_name} every {interval_seconds} seconds")
            return f"Scheduled sync for {profile_name} every {interval_seconds} seconds (Task ID: {task_id})"
            
        except Exception as e:
            self.logger.error(f"Failed to start scheduled sync for {profile_name}: {e}")
            raise IntegrationError(f"Scheduling failed: {e}")
    
    def _execute_sync(self, profile_name: str, profile: Dict[str, Any], 
                     adapter: Any, chain: Any) -> SyncResult:
        """Execute synchronization task"""
        result = SyncResult(
            profile_name=profile_name,
            status=SyncStatus.SYNCING,
            events_processed=0,
            start_time=time.time()
        )
        
        try:
            # Fetch changes from ERP
            erp_events = adapter.get_changes_since_last_sync()
            
            # Translate and submit to blockchain
            for erp_event in erp_events:
                try:
                    bc_event = self.translate_erp_to_blockchain(erp_event, profile_name)
                    if chain:
                        chain.add_event(bc_event)
                    result.events_processed += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process event {erp_event.get('id', 'unknown')}: {e}"
                    result.errors.append(error_msg)
                    self.logger.warning(error_msg)
            
            # Update last sync timestamp
            self.sync_scheduler.update_last_sync(profile_name, time.time())
            result.status = SyncStatus.COMPLETED
            result.end_time = time.time()
            
            self.logger.info(f"Sync completed for {profile_name}: {result.events_processed} events processed")
            
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.end_time = time.time()
            error_msg = f"Sync failed for {profile_name}: {e}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
            
            # Schedule retry
            self.sync_scheduler.schedule_retry(profile_name)
        
        return result
    
    def get_sync_status(self, profile_name: str) -> Dict[str, Any]:
        """Get synchronization status for a profile"""
        return self.sync_scheduler.get_status(profile_name)
    
    def stop_scheduled_sync(self, profile_name: str) -> bool:
        """Stop scheduled synchronization"""
        return self.sync_scheduler.stop_task(profile_name)
    
    # Built-in transformers
    def _transform_date(self, value: Any, params: Optional[Dict[str, Any]] = None) -> str:
        """Transform date values"""
        if params and "format" in params:
            try:
                return datetime.strptime(str(value), params["format"]).isoformat()
            except ValueError:
                self.logger.warning(f"Invalid date format: {value}")
                return str(value)
        return str(value)
    
    def _transform_amount(self, value: Any, params: Optional[Dict[str, Any]] = None) -> float:
        """Transform amount values"""
        try:
            if params and "currency_conversion" in params:
                # In a real implementation, this would do currency conversion
                pass
            return float(value)
        except (ValueError, TypeError):
            self.logger.warning(f"Invalid amount value: {value}")
            return 0.0
    
    @staticmethod
    def _transform_id(value: Any, params: Optional[Dict[str, Any]] = None) -> str:
        """Transform ID values"""
        if params and "prefix" in params:
            return f"{params['prefix']}{value}"
        return str(value)
    
    @staticmethod
    def _transform_status(value: Any, params: Optional[Dict[str, Any]] = None) -> str:
        """Transform status values"""
        if params and "mapping" in params:
            return params["mapping"].get(str(value), str(value))
        return str(value)
    
    @staticmethod
    def _transform_currency(value: Any, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Transform currency values"""
        return {
            "amount": float(value),
            "currency": params.get("target_currency", "USD") if params else "USD"
        }
    
    @staticmethod
    def _transform_boolean(value: Any, params: Optional[Dict[str, Any]] = None) -> bool:
        """Transform boolean values"""
        if isinstance(value, bool):
            return value
        
        str_value = str(value).lower()
        return str_value in ["true", "1", "yes", "on", "active"]


class MappingEngine:
    """Mapping rules engine for field transformation"""
    
    def __init__(self):
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.transformers: Dict[str, Callable] = {}
        self.lock = threading.Lock()
    
    def register_transformer(self, name: str, transformer_func: Callable):
        """Register a field transformer function"""
        with self.lock:
            self.transformers[name] = transformer_func
    
    def create_profile(self, profile_name: str, erp_system: str, 
                      mapping_rules: Dict[str, Any]) -> str:
        """Create a new mapping profile"""
        with self.lock:
            # Validate mapping rules
            self._validate_mapping_rules(mapping_rules)
            
            self.profiles[profile_name] = {
                "erp_system": erp_system,
                "mapping_rules": mapping_rules,
                "created_at": time.time(),
                "last_updated": time.time()
            }
            return profile_name
    
    def update_profile(self, profile_name: str, mapping_rules: Dict[str, Any]) -> bool:
        """Update existing mapping profile"""
        with self.lock:
            if profile_name not in self.profiles:
                return False
            
            self._validate_mapping_rules(mapping_rules)
            self.profiles[profile_name]["mapping_rules"] = mapping_rules
            self.profiles[profile_name]["last_updated"] = time.time()
            return True
    
    def get_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Get mapping profile"""
        with self.lock:
            return self.profiles.get(profile_name)
    
    def delete_profile(self, profile_name: str) -> bool:
        """Delete mapping profile"""
        with self.lock:
            if profile_name in self.profiles:
                del self.profiles[profile_name]
                return True
            return False
    
    def list_profiles(self) -> List[str]:
        """List all profile names"""
        with self.lock:
            return list(self.profiles.keys())
    
    def _validate_mapping_rules(self, mapping_rules: Dict[str, Any]):
        """Validate mapping rule structure"""
        for bc_field, rule in mapping_rules.items():
            if isinstance(rule, str):
                # Simple path mapping
                continue
            elif isinstance(rule, dict):
                # Complex rule with transformer
                if "source_path" not in rule:
                    raise MappingError(f"Missing source_path for {bc_field}")
                if "transformer" in rule and rule["transformer"] not in self.transformers:
                    raise MappingError(f"Invalid transformer {rule['transformer']}")
            else:
                raise MappingError(f"Invalid rule format for {bc_field}")


class EventTranslator:
    """Translates ERP events to blockchain events"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def translate(self, erp_event: Dict[str, Any], mapping_rules: Dict[str, Any]) -> Dict[str, Any]:
        """Translate ERP event using mapping rules"""
        blockchain_event = {}
        
        for bc_field, rule in mapping_rules.items():
            try:
                if isinstance(rule, str):
                    # Simple path mapping
                    value = self._get_nested_value(erp_event, rule)
                elif isinstance(rule, dict):
                    # Complex rule with transformer
                    value = self._get_nested_value(erp_event, rule["source_path"])
                    if "transformer" in rule:
                        transformer = self._get_transformer(rule["transformer"])
                        if transformer:
                            value = transformer(value, rule.get("params"))
                else:
                    continue
                    
                # Set the value in blockchain event
                if value is not None:
                    self._set_nested_value(blockchain_event, bc_field, value)
                    
            except Exception as e:
                self.logger.warning(f"Failed to map field {bc_field}: {e}")
        
        # Add required blockchain metadata
        blockchain_event.setdefault("timestamp", time.time())
        blockchain_event.setdefault("event", "erp_integration")
        blockchain_event.setdefault("source", "erp_system")
        
        return blockchain_event
    
    @staticmethod
    def _get_nested_value(obj: Dict[str, Any], path: str) -> Any:
        """Get value from nested object using path notation"""
        if not path:
            return None
            
        parts = path.split('.')
        current = obj
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None
        
        return current
    
    @staticmethod
    def _set_nested_value(obj: Dict[str, Any], path: str, value: Any):
        """Set value in nested object using path notation"""
        if not path:
            return
            
        parts = path.split('.')
        current = obj
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
    
    @staticmethod
    def _get_transformer(name: str) -> Optional[Callable]:
        """Get transformer function by name"""
        # This would typically reference the mapping engine's transformers
        # For now, return a simple identity function
        return lambda v, p: v


class ChangeDetector:
    """Detects meaningful changes in ERP data"""
    
    def __init__(self):
        self.previous_states: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def detect_changes(self, erp_event: Dict[str, Any], 
                      profile: Dict[str, Any]) -> Dict[str, Any]:
        """Detect changes in ERP event and add change metadata"""
        entity_key = self._get_entity_key(erp_event, profile)
        
        with self.lock:
            previous_state = self.previous_states.get(entity_key)
            
            if previous_state:
                changes = self._compare_states(previous_state, erp_event)
                if changes:
                    erp_event["changes"] = changes
                    erp_event["change_detected"] = True
                else:
                    erp_event["change_detected"] = False
            else:
                erp_event["change_detected"] = True
                erp_event["changes"] = {"type": "new_entity"}
            
            # Update stored state
            self.previous_states[entity_key] = erp_event.copy()
            
        return erp_event
    
    @staticmethod
    def _get_entity_key(erp_event: Dict[str, Any],
                        profile: Dict[str, Any]) -> str:
        """Generate unique key for entity"""
        key_fields = profile.get("key_fields", ["id"])
        key_values = []
        
        for field in key_fields:
            value = erp_event.get(field, "unknown")
            key_values.append(str(value))
        
        return ":".join(key_values)
    
    @staticmethod
    def _compare_states(old_state: Dict[str, Any],
                        new_state: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two states and return differences"""
        changes = {}
        
        # Check for modified fields
        for key, new_value in new_state.items():
            if key in old_state:
                old_value = old_state[key]
                if old_value != new_value:
                    changes[key] = {
                        "old": old_value,
                        "new": new_value,
                        "type": "modified"
                    }
            else:
                changes[key] = {
                    "new": new_value,
                    "type": "added"
                }
        
        # Check for removed fields
        for key, old_value in old_state.items():
            if key not in new_state:
                changes[key] = {
                    "old": old_value,
                    "type": "removed"
                }
        
        return changes


class SyncScheduler:
    """Schedules and manages synchronization tasks"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self._shutdown = False
    
    def schedule_task(self, profile_name: str, task_func: Callable, 
                     interval_seconds: int) -> str:
        """Schedule a synchronization task"""
        with self.lock:
            if self._shutdown:
                raise IntegrationError("Scheduler is shutdown")
            
            task_id = f"{profile_name}_{int(time.time())}"
            
            # Stop existing task if any
            if profile_name in self.tasks:
                self._stop_task_internal(profile_name)
            
            # Create new task
            task_info = {
                "task_id": task_id,
                "profile_name": profile_name,
                "task_func": task_func,
                "interval": interval_seconds,
                "last_sync": 0,
                "next_sync": time.time() + interval_seconds,
                "status": SyncStatus.IDLE,
                "retry_count": 0,
                "max_retries": 3,
                "created_at": time.time()
            }
            
            self.tasks[profile_name] = task_info
            
            # Start the task
            self._schedule_next_execution(profile_name)
            
            return task_id
    
    def _schedule_next_execution(self, profile_name: str):
        """Schedule next execution of a task"""
        if self._shutdown or profile_name not in self.tasks:
            return
        
        task_info = self.tasks[profile_name]
        delay = max(0, task_info["next_sync"] - time.time())
        
        def execute_task():
            if self._shutdown or profile_name not in self.tasks:
                return
            
            task_info = self.tasks[profile_name]
            task_info["status"] = SyncStatus.SYNCING
            
            try:
                # Execute the task
                result = task_info["task_func"]()
                
                if result.status == SyncStatus.COMPLETED:
                    task_info["status"] = SyncStatus.COMPLETED
                    task_info["retry_count"] = 0
                else:
                    task_info["status"] = SyncStatus.FAILED
                    task_info["retry_count"] += 1
                
                task_info["last_sync"] = time.time()
                
            except Exception as e:
                task_info["status"] = SyncStatus.FAILED
                task_info["retry_count"] += 1
                self.logger.error(f"Task execution failed for {profile_name}: {e}")
            
            # Schedule next execution
            if not self._shutdown and profile_name in self.tasks:
                task_info["next_sync"] = time.time() + task_info["interval"]
                self._schedule_next_execution(profile_name)
        
        # Schedule with thread pool
        self.executor.submit(lambda: threading.Timer(delay, execute_task).start())
    
    def stop_task(self, profile_name: str) -> bool:
        """Stop a scheduled task"""
        with self.lock:
            return self._stop_task_internal(profile_name)
    
    def _stop_task_internal(self, profile_name: str) -> bool:
        """Internal method to stop a task"""
        if profile_name in self.tasks:
            del self.tasks[profile_name]
            self.logger.info(f"Stopped sync task for {profile_name}")
            return True
        return False
    
    def update_last_sync(self, profile_name: str, timestamp: float):
        """Update last sync timestamp"""
        with self.lock:
            if profile_name in self.tasks:
                self.tasks[profile_name]["last_sync"] = timestamp
    
    def schedule_retry(self, profile_name: str):
        """Schedule retry for failed sync"""
        with self.lock:
            if profile_name not in self.tasks:
                return
            
            task_info = self.tasks[profile_name]
            if task_info["retry_count"] < task_info["max_retries"]:
                # Exponential backoff
                delay = min(300, 30 * (2 ** task_info["retry_count"]))
                task_info["next_sync"] = time.time() + delay
                self.logger.info(f"Scheduling retry for {profile_name} in {delay} seconds")
    
    def get_status(self, profile_name: str) -> Dict[str, Any]:
        """Get task status"""
        with self.lock:
            if profile_name not in self.tasks:
                return {"error": "Task not found"}
            
            task_info = self.tasks[profile_name]
            return {
                "task_id": task_info["task_id"],
                "profile_name": profile_name,
                "status": task_info["status"].value,
                "interval": task_info["interval"],
                "last_sync": task_info["last_sync"],
                "next_sync": task_info["next_sync"],
                "retry_count": task_info["retry_count"],
                "max_retries": task_info["max_retries"],
                "created_at": task_info["created_at"]
            }
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get status of all tasks"""
        with self.lock:
            return [self.get_status(profile_name) for profile_name in self.tasks.keys()]
    
    def shutdown(self):
        """Shutdown the scheduler"""
        with self.lock:
            self._shutdown = True
            self.tasks.clear()
        
        self.executor.shutdown(wait=True)
        self.logger.info("Sync scheduler shutdown complete")


# Factory functions for easy setup
def create_erp_integration() -> ERPIntegrationFramework:
    """Create ERP integration framework with default configuration"""
    return ERPIntegrationFramework()


def create_sap_integration_profile(profile_name: str, sap_config: Dict[str, Any]) -> Dict[str, Any]:
    """Create SAP integration profile template"""
    return {
        "profile_name": profile_name,
        "erp_system": "sap",
        "config": sap_config,
        "mapping_rules": {
            "entity_id": "material.document_number",
            "event": {
                "source_path": "material.event_type",
                "transformer": "status",
                "params": {
                    "mapping": {
                        "created": "creation",
                        "updated": "modification",
                        "deleted": "deletion"
                    }
                }
            },
            "details.material_id": "material.id",
            "details.quantity": {
                "source_path": "material.quantity",
                "transformer": "amount"
            },
            "details.timestamp": {
                "source_path": "material.timestamp",
                "transformer": "date",
                "params": {"format": "%Y%m%d%H%M%S"}
            }
        },
        "detect_changes": True,
        "key_fields": ["material.document_number"]
    }