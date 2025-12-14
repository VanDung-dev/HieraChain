"""
Utility functions for HieraChain Framework.

This module provides common utility functions used throughout the framework,
including cryptographic utilities, validation helpers, and data processing functions.
"""

import hashlib
import json
import time
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime


def compute_hash_standalone(data_string: str) -> str:
    """
    Pure function to compute SHA-256 hash. 
    This is top-level to be picklable for multiprocessing.
    """
    return hashlib.sha256(data_string.encode()).hexdigest()

def compute_merkle_leaves_standalone(data_list_strings: List[str]) -> List[str]:
    """
    Pure function to compute multiple SHA-256 hashes in a batch.
    Designed for running in a worker process to amortize IPC cost.
    """
    return [hashlib.sha256(s.encode()).hexdigest() for s in data_list_strings]

def compute_leaves_from_events_standalone(events: List[Dict[str, Any]]) -> List[str]:
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

def generate_hash(data: Union[str, Dict[str, Any]]) -> str:
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
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}-{timestamp}-{unique_id}"


def generate_proof_hash(block_hash: str, metadata: Dict[str, Any]) -> str:
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


def validate_event_structure(event: Dict[str, Any]) -> bool:
    """
    Validate event structure according to framework guidelines.
    
    Args:
        event: Event dictionary to validate
        
    Returns:
        True if event structure is valid, False otherwise
    """
    if not isinstance(event, dict):
        return False
    
    # Required fields
    required_fields = ["event", "timestamp"]
    for field in required_fields:
        if field not in event:
            return False
    
    # Event type should be string
    if not isinstance(event["event"], str):
        return False
    
    # Timestamp should be numeric
    if not isinstance(event["timestamp"], (int, float)):
        return False
    
    # If entity_id is present, it should be string (metadata field)
    if "entity_id" in event and not isinstance(event["entity_id"], str):
        return False
    
    return True


def validate_proof_metadata(metadata: Dict[str, Any]) -> bool:
    """
    Validate proof metadata for Main Chain submission.
    
    Args:
        metadata: Metadata dictionary to validate
        
    Returns:
        True if metadata is valid, False otherwise
    """
    if not isinstance(metadata, dict):
        return False
    
    # Should contain summary information, not detailed domain data
    forbidden_detailed_fields = [
        "full_details", "raw_data", "complete_record",
        "internal_data", "complete_log", "detailed_data"
    ]
    for field in forbidden_detailed_fields:
        if field in metadata:
            return False
    
    # Check for nested detailed data that shouldn't be in Main Chain
    for key, value in metadata.items():
        if isinstance(value, dict):
            # If any value is a dict, it's considered detailed data
            # unless it's a small summary object
            if len(value) > 5:  # More than 5 keys is considered detailed
                return False
            # Recursively check nested dictionaries
            if not validate_proof_metadata(value):
                return False
        elif isinstance(value, list) and len(value) > 10:
            # Large lists are considered detailed data
            return False
            
    return True


def create_event(entity_id: str, event_type: str, details: Optional[Dict[str, Any]] = None,
                timestamp: Optional[float] = None) -> Dict[str, Any]:
    """
    Create a properly structured event following framework guidelines.
    
    Args:
        entity_id: Entity identifier (used as metadata)
        event_type: Type of event
        details: Additional event details
        timestamp: Event timestamp (defaults to current time)
        
    Returns:
        Properly structured event dictionary
    """
    event: Dict[str, Any] = {
        "entity_id": entity_id,  # Metadata field, not block identifier
        "event": event_type,
        "timestamp": timestamp or time.time()
    }
    
    if details:
        event["details"] = details
    
    return event


def filter_events_by_timerange(events: List[Dict[str, Any]], 
                              start_time: float, end_time: float) -> List[Dict[str, Any]]:
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


def group_events_by_entity(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group events by entity_id.
    
    Args:
        events: List of events to group
        
    Returns:
        Dictionary mapping entity_id to list of events
    """
    grouped = {}
    for event in events:
        entity_id = event.get("entity_id", "unknown")
        if entity_id not in grouped:
            grouped[entity_id] = []
        grouped[entity_id].append(event)
    
    return grouped


def group_events_by_type(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group events by event type.
    
    Args:
        events: List of events to group
        
    Returns:
        Dictionary mapping event type to list of events
    """
    grouped = {}
    for event in events:
        event_type = event.get("event", "unknown")
        if event_type not in grouped:
            grouped[event_type] = []
        grouped[event_type].append(event)
    
    return grouped


def calculate_chain_integrity_score(chain_data: List[Dict[str, Any]]) -> float:
    """
    Calculate integrity score for a blockchain.
    
    Args:
        chain_data: List of block dictionaries
        
    Returns:
        Integrity score between 0.0 and 1.0
    """
    if not chain_data:
        return 0.0
    
    valid_blocks = 0
    total_blocks = len(chain_data)
    
    for i, block in enumerate(chain_data):
        # Check basic block structure
        required_fields = ["index", "events", "timestamp", "previous_hash", "hash"]
        if all(field in block for field in required_fields):
            # Check if events is a list (not single event)
            if isinstance(block["events"], list):
                # Check if hash is consistent
                recalculated_hash = generate_hash({
                    "index": block["index"],
                    "events": block["events"],
                    "timestamp": block["timestamp"],
                    "previous_hash": block["previous_hash"],
                    "nonce": block.get("nonce", 0)
                })
                
                if recalculated_hash == block["hash"]:
                    valid_blocks += 1
    
    return valid_blocks / total_blocks


def format_timestamp(timestamp: float) -> str:
    """
    Format timestamp for human-readable display.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Formatted timestamp string
    """
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def sanitize_metadata_for_main_chain(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata for Main Chain submission by removing detailed data.
    
    Args:
        metadata: Original metadata dictionary
        
    Returns:
        Sanitized metadata suitable for Main Chain
    """
    # Fields that should be removed for Main Chain (too detailed)
    detailed_fields = [
        "full_details", "raw_data", "complete_record", "individual_events",
        "detailed_logs", "complete_history", "full_trace"
    ]
    
    sanitized = {}
    for key, value in metadata.items():
        if key not in detailed_fields:
            # Keep only summary-level information
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, dict) and len(value) <= 5:  # Small summary objects
                sanitized[key] = value
            elif isinstance(value, list) and len(value) <= 10:  # Small summary lists
                sanitized[key] = value
    
    return sanitized


def create_domain_event_template(domain_type: str) -> Dict[str, Any]:
    """
    Create a template for domain-specific events.
    
    Args:
        domain_type: Type of domain (e.g., "supply_chain", "healthcare")
        
    Returns:
        Event template dictionary
    """
    return {
        "entity_id": f"{domain_type.upper()}-{int(time.time())}-{str(uuid.uuid4())[:8]}",
        "event": "template_event",
        "timestamp": time.time(),
        "details": {
            "domain_type": domain_type,
            "created_by": "framework_template"
        }
    }


def validate_no_cryptocurrency_terms(data: Union[str, Dict[str, Any]]) -> bool:
    """
    Validate that data doesn't contain cryptocurrency terminology.
    
    Args:
        data: Data to validate (string or dictionary)
        
    Returns:
        True if no cryptocurrency terms found, False otherwise
    """
    # Forbidden cryptocurrency terms
    crypto_terms = [
        "transaction", "mining", "coin", "token", "wallet", "address",
        "sender", "receiver", "amount", "fee", "reward", "coinbase"
    ]
    
    # Convert data to string for checking
    if isinstance(data, dict):
        data_string = json.dumps(data).lower()
    else:
        data_string = str(data).lower()
    
    # Check for forbidden terms
    for term in crypto_terms:
        if term in data_string:
            return False
    
    return True


class MerkleTree:
    """
    Merkle Tree implementation for efficient data verification and hashing.
    """
    
    def __init__(self, data_list: List[Union[str, Dict[str, Any]]] = None, leaves: List[str] = None):
        """
        Initialize Merkle Tree.
        
        Args:
            data_list: List of data items (strings or dicts) to include in the tree (will be hashed)
            leaves: List of pre-calculated hashes (hex strings). If provided, data_list is ignored.
        """
        if leaves is not None:
            self.leaves = leaves
        elif data_list is not None:
            self.leaves = [generate_hash(data) for data in data_list]
        else:
            self.leaves = []
            
        self.root = self._build_tree(self.leaves)

    def _build_tree(self, nodes: List[str]) -> str:
        """
        Recursively build the Merkle Tree.
        
        Args:
            nodes: List of hash nodes at the current level
            
        Returns:
            Root hash of the tree
        """
        if not nodes:
            return hashlib.sha256(b"").hexdigest() # Empty tree hash
            
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
