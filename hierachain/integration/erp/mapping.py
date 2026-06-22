"""
Mapping engine and event translation helper functions for ERP Integration.
"""

import time
import logging
import threading
from typing import Any, Callable

from hierachain.integration.types import MappingError

logger = logging.getLogger(__name__)


def get_nested_value(obj: Any, path: str) -> Any:
    """Get value from nested object using path notation (e.g., 'a.b.0.c')"""
    if not path or obj is None:
        return None
        
    current = obj
    for part in path.split('.'):
        current = _get_next_level(current, part)
        if current is None:
            return None
    return current


def _get_next_level(current: Any, part: str) -> Any:
    """Helper to get the next level in a nested structure (dict or list)"""
    if isinstance(current, dict):
        return current.get(part)
    if isinstance(current, list) and part.isdigit():
        index = int(part)
        return current[index] if 0 <= index < len(current) else None
    return None


def set_nested_value(obj: dict[str, Any], path: str, value: Any):
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


def add_blockchain_metadata(blockchain_event: dict[str, Any]):
    """Add required blockchain metadata to the event"""
    blockchain_event.setdefault("timestamp", time.time())
    blockchain_event.setdefault("event", "erp_integration")
    blockchain_event.setdefault("source", "erp_system")


# Helper functions for ERP integration
def transform_id(value: Any, params: dict[str, Any] | None = None) -> str:
    """Transform ID values"""
    if params and "prefix" in params:
        return f"{params['prefix']}{value}"
    return str(value)


def transform_status(value: Any, params: dict[str, Any] | None = None) -> str:
    """Transform status values"""
    if params and "mapping" in params:
        return params["mapping"].get(str(value), str(value))
    return str(value)


def transform_currency(
    value: Any, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Transform currency values"""
    return {
        "amount": float(value),
        "currency": params.get("target_currency", "USD") if params else "USD"
    }


def transform_boolean(value: Any, _params: dict[str, Any] | None = None) -> bool:
    """Transform boolean values"""
    if isinstance(value, bool):
        return value
    
    str_value = str(value).lower()
    return str_value in ["true", "1", "yes", "on", "active"]


class MappingEngine:
    """Mapping rules engine for field transformation"""
    
    def __init__(self):
        self.profiles: dict[str, dict[str, Any]] = {}
        self.transformers: dict[str, Callable] = {}
        self.lock = threading.Lock()
    
    def register_transformer(self, name: str, transformer_func: Callable) -> None:
        """Register a field transformer function"""
        with self.lock:
            self.transformers[name] = transformer_func
    
    def create_profile(
        self,
        profile_name: str,
        erp_system: str,
        mapping_rules: dict[str, Any]
    ) -> str:
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
    
    def update_profile(self, profile_name: str, mapping_rules: dict[str, Any]) -> bool:
        """Update existing mapping profile"""
        with self.lock:
            if profile_name not in self.profiles:
                return False
            
            self._validate_mapping_rules(mapping_rules)
            self.profiles[profile_name]["mapping_rules"] = mapping_rules
            self.profiles[profile_name]["last_updated"] = time.time()
            return True
    
    def get_profile(self, profile_name: str) -> dict[str, Any] | None:
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
    
    def list_profiles(self) -> list[str]:
        """list all profile names"""
        with self.lock:
            return list(self.profiles.keys())
    
    def _validate_mapping_rules(self, mapping_rules: dict[str, Any]) -> None:
        """Validate mapping rule structure"""
        for bc_field, rule in mapping_rules.items():
            self._validate_single_rule(bc_field, rule)

    def _validate_single_rule(self, bc_field: str, rule: Any) -> None:
        """Validate a single mapping rule"""
        if isinstance(rule, str):
            # Simple path mapping
            return
            
        if not isinstance(rule, dict):
            raise MappingError(f"Invalid rule format for {bc_field}")
            
        # Complex rule with transformer
        if "source_path" not in rule:
            raise MappingError(f"Missing source_path for {bc_field}")
            
        transformer = rule.get("transformer")
        if transformer and transformer not in self.transformers:
            raise MappingError(f"Invalid transformer {transformer}")


class EventTranslator:
    """Translates ERP events to blockchain events"""
    
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
    
    def translate(
        self, erp_event: dict[str, Any], mapping_rules: dict[str, Any]
    ) -> dict[str, Any]:
        """Translate ERP event using mapping rules"""
        blockchain_event = {}
        
        for bc_field, rule in mapping_rules.items():
            try:
                value = self._apply_rule(erp_event, rule)
                if value is not None:
                    set_nested_value(blockchain_event, bc_field, value)
            except Exception as e:
                self.logger.warning(
                    "Failed to map field %s: %s", bc_field, e
                )
        
        add_blockchain_metadata(blockchain_event)
        return blockchain_event

    @staticmethod
    def _apply_rule(erp_event: dict[str, Any], rule: Any) -> Any:
        """Apply a single mapping rule to get a value from erp_event"""
        if isinstance(rule, str):
            return get_nested_value(erp_event, rule)
            
        if isinstance(rule, dict):
            return _handle_complex_rule(erp_event, rule)
            
        return None


def _handle_complex_rule(erp_event: dict[str, Any], rule: dict[str, Any]) -> Any:
    """Handle a complex mapping rule with potential transformer"""
    source_path = str(rule.get("source_path", ""))
    if not source_path:
        return None
        
    value = get_nested_value(erp_event, source_path)
    
    transformer_name = rule.get("transformer")
    if transformer_name:
        # Identity transformer (no transformation)
        def identity_transform(v, _p):
            return v
        return identity_transform(value, rule.get("params"))
    return value
