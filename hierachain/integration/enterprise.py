"""
Enterprise Integration Module

This module provides integration capabilities with major ERP systems including
SAP, Oracle, and Microsoft Dynamics. It handles the conversion of enterprise
business events into blockchain-compatible events while maintaining the
hierarchical structure where sub-chain events are later summarized on the
main chain.
"""

import logging
import time
from typing import Any

from hierachain.integration.erp.mapping import set_nested_value
from hierachain.integration.types import IntegrationError

logger = logging.getLogger(__name__)


def _get_nested_value(data: dict[str, Any], path: str) -> Any:
    """Get nested value from dictionary using dot notation path"""
    keys = path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


class BaseERPIntegration:
    """Base class for explicitly opted-in synthetic ERP fixtures."""
    
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to ERP system"""
        raise NotImplementedError("Subclasses must implement connect method")
    
    def disconnect(self):
        """Disconnect from ERP system"""
        self.connected = False
    
    def get_events(self) -> list[dict[str, Any]]:
        """Get events from ERP system"""
        raise NotImplementedError("Subclasses must implement get_events method")
    
    def is_connected(self) -> bool:
        """Check if connected to ERP system"""
        return self.connected

    def _require_simulation_mode(self, vendor: str) -> None:
        if self.config.get("simulation_mode") is not True:
            raise IntegrationError(
                f"{vendor} fixture connector is simulation-only; "
                "set simulation_mode=True to opt in"
            )

    def _connect_simulation(self, vendor: str) -> bool:
        self._require_simulation_mode(vendor)
        self.connected = True
        return True


class SAPIntegration(BaseERPIntegration):
    """SAP-shaped fixture connector for tests and demonstrations."""
    
    def connect(self) -> bool:
        """Enable synthetic records only when simulation mode is explicit."""
        return self._connect_simulation("SAP")
    
    def get_events(self) -> list[dict[str, Any]]:
        """Get events from SAP system"""
        if not self.connected:
            raise IntegrationError("Not connected to SAP system")
        self._require_simulation_mode("SAP")
        return [
            {
                "material": {
                    "document_number": "MAT-001",
                    "event_type": "material_receipt",
                    "id": "MATERIAL-001",
                    "quantity": 100
                },
                "timestamp": time.time()
            }
        ]


class OracleIntegration(BaseERPIntegration):
    """Oracle-shaped fixture connector for tests and demonstrations."""
    
    def connect(self) -> bool:
        """Enable synthetic records only when simulation mode is explicit."""
        return self._connect_simulation("Oracle")
    
    def get_events(self) -> list[dict[str, Any]]:
        """Get events from Oracle system"""
        if not self.connected:
            raise IntegrationError("Not connected to Oracle system")
        self._require_simulation_mode("Oracle")
        return [
            {
                "record": {
                    "id": "REC-001",
                    "type": "purchase_order",
                    "total_value": 5000,
                    "vendor": "VENDOR-001"
                },
                "timestamp": time.time()
            }
        ]


class DynamicsIntegration(BaseERPIntegration):
    """Dynamics-shaped fixture connector for tests and demonstrations."""
    
    def connect(self) -> bool:
        """Enable synthetic records only when simulation mode is explicit."""
        return self._connect_simulation("Microsoft Dynamics")
    
    def get_events(self) -> list[dict[str, Any]]:
        """Get events from Dynamics system"""
        if not self.connected:
            raise IntegrationError("Not connected to Dynamics system")
        
        self._require_simulation_mode("Microsoft Dynamics")
        return [
            {
                "sales": {
                    "order_id": "SO-001",
                    "event_type": "order_created",
                    "customer": "CUSTOMER-001",
                    "total": 2500
                },
                "timestamp": time.time()
            }
        ]


class EnterpriseIntegration:
    """Support for integration with existing enterprise systems"""
    
    @staticmethod
    def connect_to_erp(erp_system: str, config: dict[str, Any]) -> BaseERPIntegration:
        """Connect to ERP system"""
        # Implementation based on ERP type
        if erp_system == "sap":
            integration = SAPIntegration(config)
        elif erp_system == "oracle":
            integration = OracleIntegration(config)
        elif erp_system == "microsoft_dynamics":
            integration = DynamicsIntegration(config)
        else:
            raise IntegrationError(f"Unsupported ERP system: {erp_system}")
        
        # Connect to the system
        integration.connect()
        return integration
    
    @staticmethod
    def erp_to_blockchain_event(
        erp_event: dict[str, Any], mapping_rules: dict[str, str]
    ) -> dict[str, Any]:
        """Convert ERP event to blockchain event"""
        # Map fields according to rules
        blockchain_event = {}
        for bc_field, erp_path in mapping_rules.items():
            value = _get_nested_value(erp_event, erp_path)
            if value is not None:
                set_nested_value(blockchain_event, bc_field, value)
        
        # Add required metadata
        blockchain_event["timestamp"] = time.time()
        return blockchain_event
    
    @staticmethod
    def validate_mapping_rules(mapping_rules: dict[str, str]) -> bool:
        """Validate mapping rules format"""
        required_fields = ["entity_id", "event"]
        
        for field in required_fields:
            if field not in mapping_rules:
                return False
        
        return True
    
    @staticmethod
    def create_default_mapping(erp_system: str) -> dict[str, str]:
        """Create default mapping rules for ERP system"""
        if erp_system == "sap":
            return {
                "entity_id": "material.document_number",
                "event": "material.event_type",
                "details.material_id": "material.id",
                "details.quantity": "material.quantity"
            }
        elif erp_system == "oracle":
            return {
                "entity_id": "record.id",
                "event": "record.type",
                "details.total_value": "record.total_value",
                "details.vendor": "record.vendor"
            }
        elif erp_system == "microsoft_dynamics":
            return {
                "entity_id": "sales.order_id",
                "event": "sales.event_type",
                "details.customer": "sales.customer",
                "details.total": "sales.total"
            }
        else:
            raise IntegrationError(f"No default mapping available for {erp_system}")
    
    @staticmethod
    def batch_convert_events(
        erp_events: list[dict[str, Any]], mapping_rules: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Convert multiple ERP events to blockchain events"""
        blockchain_events = []
        for erp_event in erp_events:
            try:
                bc_event = EnterpriseIntegration.erp_to_blockchain_event(
                    erp_event, mapping_rules
                )
                blockchain_events.append(bc_event)
            except Exception as e:
                # Log error but continue processing other events
                logger.error(f"Error converting event: {e}")
                continue
        
        return blockchain_events
