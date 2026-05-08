"""
Utility functions for HieraChain Ledger.

This module provides common utility functions used throughout the Ledger,
including cryptographic utilities, validation helpers, and data processing functions.
"""

import hashlib
import json
import time
import uuid
import re
from typing import Any
from datetime import datetime


def compute_hash_standalone(data_string: str) -> str:
    """
    Pure function to compute SHA-256 hash.
    This is top-level to be picklable for multiprocessing.
    """
    return hashlib.sha256(data_string.encode()).hexdigest()


def compute_merkle_leaves_standalone(data_list_strings: list[str]) -> list[str]:
    """
    Pure function to compute multiple SHA-256 hashes in a batch.
    Designed for running in a worker process to amortize IPC cost.
    """
    return [hashlib.sha256(s.encode()).hexdigest() for s in data_list_strings]


def compute_leaves_from_events_standalone(events: list[dict[str, Any]]) -> list[str]:
    """
    Pure function to compute Merkle leaves from event dicts.
    Performs JSON serialization and hashing in the worker process.
    """
    leaves = []
    for event in events:
        # Replicate generate_hash logic for dicts
        data_string = json.dumps(event, sort_keys=True, separators=(',', ':'))
        leaves.append(hashlib.sha256(data_string.encode()).hexdigest())
    return leaves


def generate_hash(data: str | dict[str, Any]) -> str:
    """
    Generate SHA-256 hash for given data.
    
    Args:
        data: Data to hash (string or dictionary)
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    if isinstance(data, dict):
        # Convert dict to JSON string with sorted keys for consistent hashing
        data_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
    else:
        data_string = str(data)
    
    return compute_hash_standalone(data_string)


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


def filter_events_by_timerange(
    events: list[dict[str, Any]], start_time: float, end_time: float
) -> list[dict[str, Any]]:
    """
    Filter events by timestamp range.
    
    Args:
        events: List of events to filter
        start_time: Start timestamp (inclusive)
        end_time: End timestamp (inclusive)
        
    Returns:
        Filtered list of events
    """
    return [
        event for event in events
        if start_time <= event.get("timestamp", 0) <= end_time
    ]


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


def group_events_by_type(
    events: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """
    Group events by event type.
    
    Args:
        events: List of events to group
        
    Returns:
        Dictionary mapping event type to list of events
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        event_type = event.get("event", "unknown")
        if event_type not in grouped:
            grouped[event_type] = []
        grouped[event_type].append(event)
    
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


def calculate_chain_integrity_score(chain_data: list[dict[str, Any]]) -> float:
    """
    Calculate integrity score for a blockchain.
    
    Args:
        chain_data: List of block dictionaries
        
    Returns:
        Integrity score between 0.0 and 1.0
    """
    if not chain_data:
        return 0.0
    
    valid_blocks = sum(1 for block in chain_data if _is_block_valid(block))
    return valid_blocks / len(chain_data)


def format_timestamp(timestamp: float) -> str:
    """
    Format timestamp for human-readable display.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Formatted timestamp string
    """
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


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


def create_domain_event_template(domain_type: str) -> dict[str, Any]:
    """
    Create a template for domain-specific events.
    
    Args:
        domain_type: Type of domain (e.g., "supply_chain", "healthcare")
        
    Returns:
        Event template dictionary
    """
    return {
        "entity_id": (
            f"{domain_type.upper()}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        ),
        "event": "template_event",
        "timestamp": time.time(),
        "details": {
            "domain_type": domain_type,
            "created_by": "Ledger_template"
        }
    }


def validate_no_cryptocurrency_terms(data: Any) -> bool:
    """
    Validate that data doesn't contain standalone cryptocurrency terminology.
    This function recursively checks strings, dictionaries, and lists.
    
    Args:
        data: Data to validate (string, dictionary, list, or other)
        
    Returns:
        True if no cryptocurrency terms found, False otherwise
    """
    # Forbidden cryptocurrency terms
    crypto_terms = [
        "transaction", "mining", "coin", "token", "wallet", "address",
        "sender", "receiver", "amount", "fee", "reward", "coinbase"
    ]
    
    # Process data to check for whole words
    if isinstance(data, dict):
        # Check both keys and values in dictionary
        for key, value in data.items():
            if not validate_no_cryptocurrency_terms(str(key)):
                return False
            if isinstance(value, (dict, list)):
                if not validate_no_cryptocurrency_terms(value):
                    return False
            else:
                if not validate_no_cryptocurrency_terms(str(value)):
                    return False
        return True
    
    if isinstance(data, list):
        for item in data:
            if not validate_no_cryptocurrency_terms(item):
                return False
        return True

    # For strings, use word boundaries
    data_string = str(data).lower()
    for term in crypto_terms:
        # Use regex to check for whole word match only
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, data_string):
            return False
            
    return True


class MerkleTree:
    """
    Merkle Tree implementation for efficient data verification and hashing.
    """
    
    def __init__(
        self,
        data_list: list[str | dict[str, Any]] | None = None,
        leaves: list[str] | None = None
    ):
        """
        Initialize Merkle Tree.
        
        Args:
            data_list: List of data items (strings or dicts) to include
                       in the tree (will be hashed)
            leaves: List of pre-calculated hashes (hex strings). If provided,
                    data_list is ignored.
        """
        if leaves is not None:
            self.leaves = leaves
        elif data_list is not None:
            self.leaves = [generate_hash(data) for data in data_list]
        else:
            self.leaves = []
            
        self.root = self._build_tree(self.leaves)

    def _build_tree(self, nodes: list[str]) -> str:
        """
        Recursively build the Merkle Tree.
        
        Args:
            nodes: List of hash nodes at the current level
            
        Returns:
            Root hash of the tree
        """
        if not nodes:
            # Empty tree hash
            return hashlib.sha256(b"").hexdigest()
            
        if len(nodes) == 1:
            return nodes[0]
        
        new_level = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            # Duplicate last node if number of nodes is odd
            right = nodes[i+1] if i+1 < len(nodes) else left
            
            # Combine hashes
            combined = left + right
            new_level.append(hashlib.sha256(combined.encode()).hexdigest())
            
        return self._build_tree(new_level)

    def get_root(self) -> str:
        """Get the Merkle Root hash."""
        return self.root
