"""
Enterprise Integration Module

This module provides integration capabilities with major ERP systems including SAP, Oracle, 
and Microsoft Dynamics. It handles the conversion of enterprise business events into 
blockchain-compatible events while maintaining the hierarchical structure where sub-chain 
events are later summarized on the main chain.
"""
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Exception raised for integration-related errors"""
    pass


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
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
    """Base class for ERP system integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to ERP system"""
        raise NotImplementedError("Subclasses must implement connect method")
    
    def disconnect(self):
        """Disconnect from ERP system"""
        self.connected = False
    
    def get_events(self, last_hours: int = 24) -> List[Dict[str, Any]]:
        """Get events from ERP system"""
        raise NotImplementedError("Subclasses must implement get_events method")
    
    def is_connected(self) -> bool:
        """Check if connected to ERP system"""
        return self.connected


class SAPIntegration(BaseERPIntegration):
    """SAP ERP system integration"""
    
    def connect(self) -> bool:
        """Connect to SAP system"""
        # Placeholder implementation
        # In real implementation, this would use SAP RFC or REST API
        url = self.config.get("url")
        username = self.config.get("username")
        password = self.config.get("password")
        
        if not all([url, username, password]):
            raise IntegrationError("Missing required SAP connection parameters")
        
        # Simulate connection
        self.connected = True
        return True
    
    def get_events(self, last_hours: int = 24) -> List[Dict[str, Any]]:
        """Get events from SAP system"""
        if not self.connected:
            raise IntegrationError("Not connected to SAP system")
        
        # Placeholder implementation
        # In real implementation, this would query SAP tables/APIs
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
    """Oracle ERP system integration"""
    
    def connect(self) -> bool:
        """Connect to Oracle system"""
        # Placeholder implementation
        url = self.config.get("url")
        username = self.config.get("username")
        password = self.config.get("password")
        
        if not all([url, username, password]):
            raise IntegrationError("Missing required Oracle connection parameters")
        
        self.connected = True
        return True
    
    def get_events(self, last_hours: int = 24) -> List[Dict[str, Any]]:
        """Get events from Oracle system"""
        if not self.connected:
            raise IntegrationError("Not connected to Oracle system")
        
        # Placeholder implementation
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
    """Microsoft Dynamics ERP system integration"""
    
    def connect(self) -> bool:
        """Connect to Dynamics system"""
        # Placeholder implementation
        url = self.config.get("url")
        username = self.config.get("username")
        password = self.config.get("password")
        
        if not all([url, username, password]):
            raise IntegrationError("Missing required Dynamics connection parameters")
        
        self.connected = True
        return True
    
    def get_events(self, last_hours: int = 24) -> List[Dict[str, Any]]:
        """Get events from Dynamics system"""
        if not self.connected:
            raise IntegrationError("Not connected to Dynamics system")
        
        # Placeholder implementation
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
    def connect_to_erp(erp_system: str, config: Dict[str, Any]) -> BaseERPIntegration:
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
    def erp_to_blockchain_event(erp_event: Dict[str, Any], mapping_rules: Dict[str, str]) -> Dict[str, Any]:
        """Convert ERP event to blockchain event"""
        # Map fields according to rules
        blockchain_event = {}
        for bc_field, erp_path in mapping_rules.items():
            value = _get_nested_value(erp_event, erp_path)
            if value is not None:
                blockchain_event[bc_field] = value
        
        # Add required metadata
        blockchain_event["timestamp"] = time.time()
        return blockchain_event
    
    @staticmethod
    def validate_mapping_rules(mapping_rules: Dict[str, str]) -> bool:
        """Validate mapping rules format"""
        required_fields = ["entity_id", "event"]
        
        for field in required_fields:
            if field not in mapping_rules:
                return False
        
        return True
    
    @staticmethod
    def create_default_mapping(erp_system: str) -> Dict[str, str]:
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
    def batch_convert_events(erp_events: List[Dict[str, Any]], mapping_rules: Dict[str, str]) -> List[Dict[str, Any]]:
        """Convert multiple ERP events to blockchain events"""
        blockchain_events = []
        for erp_event in erp_events:
            try:
                bc_event = EnterpriseIntegration.erp_to_blockchain_event(erp_event, mapping_rules)
                blockchain_events.append(bc_event)
            except Exception as e:
                # Log error but continue processing other events
                logger.error(f"Error converting event: {e}")
                continue
        
        return blockchain_events