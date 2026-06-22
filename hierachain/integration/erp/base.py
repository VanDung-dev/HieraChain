"""
ERP Integration Ledger base implementation for HieraChain Ledger.
"""

import time
import threading
import logging
from datetime import datetime
from typing import Any

from hierachain.integration.types import IntegrationError, SyncStatus, SyncResult

from hierachain.integration.erp.mapping import (
    MappingEngine, 
    EventTranslator, 
    transform_id, 
    transform_status, 
    transform_currency, 
    transform_boolean,
)
from hierachain.integration.erp.change_detector import ChangeDetector
from hierachain.integration.erp.scheduler import SyncScheduler

logger = logging.getLogger(__name__)


class ERPIntegrationLedger:
    """Comprehensive ERP integration Ledger with mapping engine"""
    
    def __init__(self):
        self.adapters: dict[str, Any] = {}
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
            "id": transform_id,
            "status": transform_status,
            "currency": transform_currency,
            "boolean": transform_boolean
        }
        
        for name, func in transformers.items():
            self.mapping_engine.register_transformer(name, func)
    
    def register_adapter(self, erp_system: str, adapter_class: Any):
        """Register ERP adapter"""
        with self.lock:
            self.adapters[erp_system] = adapter_class
            self.logger.info("Registered adapter for %s", erp_system)
    
    def create_mapping_profile(
        self,
        profile_name: str,
        erp_system: str,
        mapping_rules: dict[str, Any]
    ) -> str:
        """Create mapping profile for ERP integration"""
        try:
            with self.lock:
                return self.mapping_engine.create_profile(
                    profile_name, 
                    erp_system,
                    mapping_rules
                )
        except Exception as e:
            self.logger.error(
                "Failed to create mapping profile %s: %s", profile_name, e
            )
            raise IntegrationError(f"Profile creation failed: {e}")
    
    def translate_erp_to_blockchain(
        self,
        erp_event: dict[str, Any],
        profile_name: str
    ) -> dict[str, Any]:
        """Translate ERP event to blockchain event"""
        try:
            with self.lock:
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
            self.logger.error(
                "Translation failed for profile %s: %s", profile_name, e
            )
            raise IntegrationError(f"Translation failed: {e}")
    
    def start_scheduled_sync(
        self,
        profile_name: str,
        interval_seconds: int,
        chain: Any = None
    ) -> str:
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
            
            # Use local non-nullable variable for Mypy
            sync_profile = profile
            
            def sync_task():
                return self._execute_sync(profile_name, sync_profile, adapter, chain)
            
            # Schedule the task
            task_id = self.sync_scheduler.schedule_task(
                profile_name,
                sync_task,
                interval_seconds
            )
            
            self.logger.info(
                "Scheduled sync for %s every %d seconds (Task ID: %s)",
                profile_name, interval_seconds, task_id
            )
            return (
                f"Scheduled sync for {profile_name} every {interval_seconds} seconds "
                f"(Task ID: {task_id})"
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to start scheduled sync for %s: %s",
                profile_name, e
            )
            raise IntegrationError(f"Scheduling failed: {e}")
    
    def _execute_sync(
        self,
        profile_name: str,
        _profile: dict[str, Any],
        adapter: Any, chain: Any
    ) -> SyncResult:
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
                    error_msg = (
                        f"Failed to process event {erp_event.get('id', 'unknown')}: {e}"
                    )
                    result.errors.append(error_msg)
                    self.logger.warning(error_msg)
            
            # Update last sync timestamp
            self.sync_scheduler.update_last_sync(profile_name, time.time())
            result.status = SyncStatus.COMPLETED
            result.end_time = time.time()
            
            # Log success
            self.logger.info(
                "Sync completed for %s: %d events processed",
                profile_name, result.events_processed
            )
            
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.end_time = time.time()
            error_msg = f"Sync failed for {profile_name}: {e}"
            result.errors.append(error_msg)
            self.logger.error(error_msg)
            
            # Schedule retry
            self.sync_scheduler.schedule_retry(profile_name)
        
        return result
    
    def get_sync_status(self, profile_name: str) -> dict[str, Any]:
        """Get synchronization status for a profile"""
        return self.sync_scheduler.get_status(profile_name)
    
    def stop_scheduled_sync(self, profile_name: str) -> bool:
        """Stop scheduled synchronization"""
        return self.sync_scheduler.stop_task(profile_name)
    
    # Built-in transformers
    def _transform_date(self, value: Any, params: dict[str, Any] | None = None) -> str:
        """Transform date values"""
        if params and "format" in params:
            try:
                return datetime.strptime(str(value), params["format"]).isoformat()
            except ValueError:
                self.logger.warning("Invalid date format: %s", value)
                return str(value)
        return str(value)
    
    def _transform_amount(
        self, value: Any, params: dict[str, Any] | None = None
    ) -> float:
        """Transform amount values"""
        try:
            if params and "currency_conversion" in params:
                # In a real implementation, this would do currency conversion
                pass
            return float(value)
        except (ValueError, TypeError):
            self.logger.warning("Invalid amount value: %s", value)
            return 0.0


# Factory functions for easy setup
def create_erp_integration() -> ERPIntegrationLedger:
    """Create ERP integration Ledger with default configuration"""
    return ERPIntegrationLedger()


def create_sap_integration_profile(
    profile_name: str, sap_config: dict[str, Any]
) -> dict[str, Any]:
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
