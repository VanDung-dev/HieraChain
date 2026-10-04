"""
Change detector and state comparison for ERP Integration.
"""

import logging
import threading
from copy import deepcopy
from typing import Any

from hierachain.integration.erp.mapping import get_nested_value

logger = logging.getLogger(__name__)


def get_entity_key(erp_event: dict[str, Any], profile: dict[str, Any]) -> str:
    """Generate unique key for entity"""
    key_fields = profile.get("key_fields", ["id"])
    if not isinstance(key_fields, (list, tuple)) or not key_fields:
        raise ValueError("ERP identity requires a non-empty list of key_fields")
    key_values = []
    
    for key_field in key_fields:
        if not isinstance(key_field, str) or not key_field:
            raise ValueError("ERP identity fields must be non-empty paths")
        value = get_nested_value(erp_event, key_field)
        if value is None or value == "":
            raise ValueError(f"Missing ERP identity field: {key_field}")
        key_values.append(str(value))
    
    return ":".join(key_values)


def compare_states(
    old_state: dict[str, Any], new_state: dict[str, Any]
) -> dict[str, Any]:
    """Compare two states and return differences"""
    changes = {}
    
    # Process additions and modifications
    _process_new_and_modified_fields(old_state, new_state, changes)
    
    # Process removals
    _process_removed_fields(old_state, new_state, changes)
    
    return changes


def _process_new_and_modified_fields(
    old_state: dict[str, Any], new_state: dict[str, Any], changes: dict[str, Any]
) -> None:
    """Helper to detect added or modified fields"""
    for key, new_value in new_state.items():
        if key in old_state:
            _check_for_modification(key, old_state[key], new_value, changes)
        else:
            changes[key] = {"new": new_value, "type": "added"}


def _check_for_modification(
    key: str, old_value: Any, new_value: Any, changes: dict[str, Any]
) -> None:
    """Helper to check if a specific field has been modified"""
    if old_value != new_value:
        changes[key] = {"old": old_value, "new": new_value, "type": "modified"}


def _process_removed_fields(
    old_state: dict[str, Any], new_state: dict[str, Any], changes: dict[str, Any]
) -> None:
    """Helper to detect removed fields"""
    for key, old_value in old_state.items():
        if key not in new_state:
            changes[key] = {"old": old_value, "type": "removed"}


class ChangeDetector:
    """Detects meaningful changes in ERP data"""
    
    def __init__(self) -> None:
        self.previous_states: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def detect_changes(
        self, erp_event: dict[str, Any], profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Detect changes in ERP event and add change metadata"""
        entity_key = get_entity_key(erp_event, profile)
        profile_scope = str(profile.get("profile_name") or profile.get("erp_system", "default"))
        state_key = f"{profile_scope}:{entity_key}"
        business_state = deepcopy(erp_event)
        business_state.pop("changes", None)
        business_state.pop("change_detected", None)
        
        with self.lock:
            previous_state = self.previous_states.get(state_key)
            
            if previous_state:
                changes = compare_states(previous_state, business_state)
                if changes:
                    erp_event["changes"] = changes
                    erp_event["change_detected"] = True
                else:
                    erp_event.pop("changes", None)
                    erp_event["change_detected"] = False
            else:
                erp_event["change_detected"] = True
                erp_event["changes"] = {"type": "new_entity"}
            
            # Snapshot business fields only; generated change metadata must not
            # make an otherwise identical record look modified on the next pass.
            self.previous_states[state_key] = business_state
            
        return erp_event
