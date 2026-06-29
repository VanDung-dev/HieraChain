"""
Event certification and validation for the HieraChain ordering service.
"""

import time
import logging
from typing import Any, Callable
import pyarrow as pa

from hierachain.config.settings import settings
from hierachain.security.verify.zk_verifier import ZKVerifier
from hierachain.consensus.ordering.types import PendingEvent
from hierachain.consensus.ordering.utils import verify_event_signature

_EVENT_SCHEMA = pa.schema([
    ('entity_id', pa.string()),
    ('event', pa.string()),
    ('timestamp', pa.float64()),
    ('details', pa.map_(pa.string(), pa.string())),
    ('details_cid', pa.string()),
    ('details_nonce', pa.string()),
    ('data', pa.binary()),
])

logger = logging.getLogger(__name__)


def _verify_zk_proof(event: PendingEvent) -> dict[str, Any]:
    """Verify ZK proof attached to an event."""
    result: dict[str, Any] = {
        "verified": False,
        "required": settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN,
        "reason": ""
    }

    zk_proof_hex = event.event_data.get("zk_proof")
    if zk_proof_hex is None:
        if settings.ZK_PROOF_REQUIRED_FOR_MAINCHAIN:
            result["reason"] = "ZK proof required but missing"
            return result
        result["verified"] = True
        result["reason"] = "ZK proof not required"
        return result
    if not isinstance(zk_proof_hex, str):
        result["reason"] = "Invalid ZK proof format"
        return result

    try:
        verifier = ZKVerifier(mode=settings.ZK_MODE)
        zk_proof = bytes.fromhex(zk_proof_hex)

        details = event.event_data.get("details", {})
        public_inputs = {
            "old_state_root": details.get("previous_state", ""),
            "new_state_root": details.get("current_state", ""),
            "block_index": details.get("block_index", 0)
        }

        verified = verifier.verify(zk_proof, public_inputs)
        result["verified"] = verified
        result["reason"] = "ZK proof valid" if verified else "ZK proof invalid"
    except Exception as e:
        result["reason"] = f"ZK verification error: {str(e)}"

    return result


def _validate_structure(event_data: Any) -> bool:
    """Validate basic event structure"""
    if isinstance(event_data, (pa.Table, pa.RecordBatch)):
        return event_data.schema.equals(_EVENT_SCHEMA)

    if not isinstance(event_data, dict):
        return False

    timestamp = event_data.get("timestamp", 0)
    current_time = time.time()
    if abs(timestamp - current_time) > 300:
        return False

    return True


_REQUIRED_FIELDS = ["entity_id", "event", "timestamp"]


def _run_custom_rules(
    rules: list[Callable],
    event_data: dict[str, Any],
    certification: dict[str, Any],
) -> None:
    """Run all custom validation rules against event data."""
    for rule in rules:
        try:
            if not rule(event_data):
                certification["valid"] = False
                certification["validation_errors"].append(
                    f"Validation rule failed: {rule.__name__}"
                )
        except Exception as e:
            certification["valid"] = False
            certification["validation_errors"].append(
                f"Validation error: {str(e)}"
            )


def _check_structure_and_fields(
    event_data: dict[str, Any], certification: dict[str, Any],
) -> None:
    """Validate event structure and required fields."""
    if not certification["valid"]:
        return

    if not _validate_structure(event_data):
        certification["valid"] = False
        certification["validation_errors"].append(
            "Invalid event structure"
        )
        return

    for field_name in _REQUIRED_FIELDS:
        if field_name not in event_data:
            certification["valid"] = False
            certification["validation_errors"].append(
                f"Missing required field: {field_name}"
            )


def _check_zk_proof(
    event: PendingEvent, certification: dict[str, Any],
) -> None:
    """Run ZK proof verification if enabled and still valid."""
    if not certification["valid"]:
        return
    if not settings.ENABLE_ZK_PROOFS:
        return

    zk_result = _verify_zk_proof(event)
    certification["zk_verified"] = zk_result["verified"]
    if not zk_result["verified"] and zk_result["required"]:
        certification["valid"] = False
        certification["validation_errors"].append(
            "ZK proof verification failed: "
            f"{zk_result['reason']}"
        )


class EventCertifier:
    """Event certification and validation"""
    
    def __init__(self) -> None:
        self.validation_rules: list[Callable] = []
        self.certified_events: dict[str, dict[str, Any]] = {}
        self._setup_default_rules()
        
    def _setup_default_rules(self) -> None:
        """Setup default validation rules"""
        def validate_default_rules(event_data: dict[str, Any]) -> bool:
            entity_id = event_data.get("entity_id", "")
            if not (isinstance(entity_id, str) and len(entity_id.strip()) > 0):
                return False
            event_type = event_data.get("event", "")
            if not (isinstance(event_type, str) and len(event_type.strip()) > 0):
                return False
            timestamp = event_data.get("timestamp")
            return isinstance(timestamp, (int, float)) and timestamp > 0
        
        self.add_validation_rule(validate_default_rules)


    def add_validation_rule(self, rule: Callable[[dict[str, Any]], bool]) -> None:
        """Add a validation rule for events"""
        self.validation_rules.append(rule)
        
    def validate(self, event: PendingEvent) -> dict[str, Any]:
        """Validate and certify an event."""
        certification: dict[str, Any] = {
            "event_id": event.event_id,
            "certified_at": time.time(),
            "valid": True,
            "validation_errors": [],
            "metadata": {},
            "zk_verified": False,
        }
        
        # 1. Custom rules
        _run_custom_rules(self.validation_rules, event.event_data, certification)

        # 2. Structure + required fields
        _check_structure_and_fields(event.event_data, certification)

        # 3. Signature verification
        if certification["valid"]:
            verify_event_signature(event, certification)

        # 4. ZK verification
        _check_zk_proof(event, certification)

        self.certified_events[event.event_id] = certification
        return certification

    def get_certification(self, event_id: str) -> dict[str, Any] | None:
        """Get certification result for an event"""
        return self.certified_events.get(event_id)
