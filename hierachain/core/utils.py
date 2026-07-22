"""
Utility functions for HieraChain Ledger.

This module provides common utility functions used throughout the Ledger,
including cryptographic utilities, validation helpers, and data processing functions.
"""

import time
import uuid
import re
import orjson
from typing import Any

from hierachain.core.merkle_tree import generate_hash


def generate_entity_id(prefix: str = "ENTITY") -> str:
    """
    Generate a unique entity identifier.
    
    Args:
        prefix: Prefix for the entity ID
        
    Returns:
        Unique entity identifier
    """
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}-{unique_id}"


def generate_proof_hash(block_hash: str, metadata: dict[str, Any]) -> str:
    """
    Generate a proof hash for Main Chain submission.
    
    Args:
        block_hash: Hash of the block being proven
        metadata: Summary metadata for the proof
        
    Returns:
        Proof hash for Main Chain storage
    """
    proof_data = {
        "block_hash": block_hash,
        "metadata": metadata
    }
    return generate_hash(proof_data)


def _check_required_fields(event: dict[str, Any]) -> bool:
    """Check if all required fields are present in the event."""
    required_fields = ["event", "timestamp", "entity_id"]
    return all(field in event for field in required_fields)


def _check_field_types(event: dict[str, Any]) -> bool:
    """Check if basic fields have correct data types."""
    if not isinstance(event["event"], str):
        return False
    if not isinstance(event["timestamp"], (int, float)):
        return False
    if not isinstance(event["entity_id"], str):
        return False
    if "details" in event and not isinstance(event["details"], dict):
        return False
    return True


def validate_event_structure(event: dict[str, Any]) -> bool:
    """
    Validate event structure according to Ledger guidelines.
    
    Args:
        event: Event dictionary to validate
        
    Returns:
        True if event structure is valid, False otherwise
    """
    if not isinstance(event, dict):
        return False
    
    # 1. Required fields
    if not _check_required_fields(event):
        return False
    
    # 2. Type validation
    if not _check_field_types(event):
        return False
    
    # 3. Content constraints
    if not validate_no_cryptocurrency_terms(event):
        return False
    
    return True


def _check_forbidden_fields(metadata: dict[str, Any]) -> bool:
    """Check for forbidden detailed fields in metadata."""
    forbidden_detailed_fields = [
        "full_details", "raw_data", "complete_record",
        "internal_data", "complete_log", "detailed_data"
    ]
    return any(field in metadata for field in forbidden_detailed_fields)


def _check_nested_structures(value: Any) -> bool:
    """Check if nested structures (dict/list) exceed summary size limits."""
    if isinstance(value, dict):
        if len(value) > 5:  # More than 5 keys is considered detailed
            return False
        # Recursively check nested dictionaries
        return validate_proof_metadata(value)
    
    if isinstance(value, list) and len(value) > 10:
        # Large lists are considered detailed data
        return False
        
    return True


def validate_proof_metadata(metadata: Any) -> bool:
    """
    Validate proof metadata for Main Chain submission.
    
    Args:
        metadata: Metadata dictionary to validate
        
    Returns:
        True if metadata is valid, False otherwise
    """
    if not isinstance(metadata, dict):
        return False
    
    # 1. Check for forbidden summary fields
    if _check_forbidden_fields(metadata):
        return False
    
    # 2. Check for nested detailed data
    for _, value in metadata.items():
        if not _check_nested_structures(value):
            return False
            
    return True


def create_event(
    entity_id: str, event_type: str,
    details: dict[str, Any] | None = None,
    timestamp: float | None = None
) -> dict[str, Any]:
    """
    Create a properly structured event following Ledger guidelines.
    
    Args:
        entity_id: Entity identifier (used as metadata)
        event_type: Type of event
        details: Additional event details
        timestamp: Event timestamp (defaults to current time)
        
    Returns:
        Properly structured event dictionary
    """
    event: dict[str, Any] = {
        "entity_id": entity_id,  # Metadata field, not block identifier
        "event": event_type,
        "timestamp": timestamp or time.time()
    }
    
    if details:
        event["details"] = details
    
    return event


def group_events_by_entity(
    events: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """
    Group events by entity_id.
    
    Args:
        events: List of events to group
        
    Returns:
        Dictionary mapping entity_id to list of events
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        entity_id = event.get("entity_id", "unknown")
        if entity_id not in grouped:
            grouped[entity_id] = []
        grouped[entity_id].append(event)
    
    return grouped


def _is_block_valid(block: dict[str, Any]) -> bool:
    """Check if a single block is valid according to Ledger rules."""
    # 1. Check basic block structure
    required_fields = ["index", "events", "timestamp", "previous_hash", "hash"]
    if not all(field in block for field in required_fields):
        return False
        
    # 2. Check if events is a list
    if not isinstance(block["events"], list):
        return False
        
    # 3. Check if hash is consistent
    recalculated_hash = generate_hash({
        "index": block["index"],
        "events": block["events"],
        "timestamp": block["timestamp"],
        "previous_hash": block["previous_hash"],
        "nonce": block.get("nonce", 0)
    })
    
    return recalculated_hash == block["hash"]


def _is_summary_value(value: Any) -> bool:
    """Check if a value is brief enough to be considered summary-level."""
    if isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, dict) and len(value) <= 5:  # Small summary objects
        return True
    if isinstance(value, list) and len(value) <= 10:  # Small summary lists
        return True
    return False


def sanitize_metadata_for_main_chain(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize metadata for Main Chain submission by removing detailed data.
    
    Args:
        metadata: Original metadata dictionary
        
    Returns:
        Sanitized metadata suitable for Main Chain
    """
    # Fields that should be removed for Main Chain (too detailed)
    detailed_fields = {
        "full_details", "raw_data", "complete_record", "individual_events",
        "detailed_logs", "complete_history", "full_trace"
    }
    
    # Fields that must always be preserved (ZK proofs)
    critical_fields = {"zk_proof", "zk_public_inputs", "proof_hash"}

    sanitized = {}
    for key, value in metadata.items():
        # 1. Always preserve critical security fields
        if key in critical_fields:
            sanitized[key] = value
            continue

        # 2. Filter out detailed fields and non-summary values
        if key not in detailed_fields and _is_summary_value(value):
            sanitized[key] = value
    
    return sanitized


# Single compiled pattern: 1 regex search vs 12 per string
_FORBIDDEN_CRYPTO_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in [
        "transaction", "mining", "coin", "token", "wallet", "address",
        "sender", "receiver", "amount", "fee", "reward", "coinbase",
    ]) + r")\b"
)


def validate_no_cryptocurrency_terms(data: Any) -> bool:
    """Validate that data doesn't contain standalone cryptocurrency terminology."""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(key, str) and _FORBIDDEN_CRYPTO_PATTERN.search(key.lower()):
                return False
            if isinstance(value, str) and _FORBIDDEN_CRYPTO_PATTERN.search(value.lower()):
                return False
            if isinstance(value, (dict, list)) and not validate_no_cryptocurrency_terms(value):
                return False
        return True
    if isinstance(data, list):
        return all(validate_no_cryptocurrency_terms(item) for item in data)
    if isinstance(data, str):
        return _FORBIDDEN_CRYPTO_PATTERN.search(data.lower()) is None
    return _FORBIDDEN_CRYPTO_PATTERN.search(str(data).lower()) is None


def get_block_events(block: Any) -> list[dict[str, Any]]:
    """
    Extract events from a block, handling plain lists, PyArrow objects,
    and blocks that expose a ``to_event_list()`` helper.
    """
    if hasattr(block, 'to_event_list'):
        return block.to_event_list()

    events_obj = getattr(block, 'events', [])

    if isinstance(events_obj, list):
        return events_obj

    # PyArrow path
    if hasattr(events_obj, 'to_pylist'):
        try:
            raw = events_obj.to_pylist()
            return [
                ev.as_py() if hasattr(ev, 'as_py') and not isinstance(ev, dict) else ev
                for ev in raw
            ]
        except (AttributeError, TypeError, ValueError):
            pass

    # Fallback: iterate
    try:
        return [
            ev.as_py() if hasattr(ev, 'as_py') else ev
            for ev in events_obj
        ]
    except (AttributeError, TypeError):
        return []

