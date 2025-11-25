"""
Block implementation for HieraChain Framework.

This module implements the Block class following the framework guidelines:
- Blocks contain multiple events, not one event per block
- Never equate a block with an entity
- Events are domain-specific operations with metadata
"""

import hashlib
import json
import time
from typing import List, Dict, Any, Optional


class Block:
    """
    Block class that contains multiple events for multiple entities.
    
    This follows the HieraChain framework guidelines where:
    - A block contains multiple events (not one event per block)
    - Events contain domain-specific data with required metadata
    - Blocks are identified by index, not by entity_id
    """
    
    def __init__(self, index: int, events: List[Dict[str, Any]], timestamp: Optional[float] = None, 
                 previous_hash: str = "", nonce: int = 0):
        """
        Initialize a new block.
        
        Args:
            index: Block index in the chain
            events: List of events (multiple events per block)
            timestamp: Block creation timestamp (defaults to current time)
            previous_hash: Hash of the previous block
            nonce: Nonce value for proof-of-work (if needed)
        """
        self.index = index
        self.events = events  # List of events - critical guideline requirement
        self.timestamp = timestamp or time.time()
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """
        Calculate the hash of the block.
        
        Returns:
            SHA-256 hash of the block data
        """
        block_data = {
            "index": self.index,
            "events": self.events,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }
        
        # Convert to JSON string with sorted keys for consistent hashing
        block_string = json.dumps(block_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def add_event(self, event: Dict[str, Any]) -> None:
        """
        Add an event to the block and recalculate hash.
        
        Args:
            event: Event dictionary with required metadata
        """
        self.events.append(event)
        self.hash = self.calculate_hash()
    
    def get_events_by_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all events for a specific entity from this block.
        
        Args:
            entity_id: The entity identifier to search for
            
        Returns:
            List of events for the specified entity
        """
        return [event for event in self.events if event.get("entity_id") == entity_id]
    
    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """
        Get all events of a specific type from this block.
        
        Args:
            event_type: The event type to search for
            
        Returns:
            List of events of the specified type
        """
        return [event for event in self.events if event.get("event") == event_type]
    
    def validate_structure(self) -> bool:
        """
        Validate the block structure according to framework guidelines.
        
        Returns:
            True if block structure is valid, False otherwise
        """
        # Check if events is a list (not a single event)
        if not isinstance(self.events, list):
            return False
        
        # Check if each event has required metadata structure
        for event in self.events:
            if not isinstance(event, dict):
                return False
            
            # Events should have entity_id as metadata (not as block identifier)
            if "entity_id" in event and not isinstance(event["entity_id"], str):
                return False
            
            # Events should have event type
            if "event" not in event:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert block to dictionary representation.
        
        Returns:
            Dictionary representation of the block
        """
        return {
            "index": self.index,
            "events": self.events,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        """
        Create a Block instance from dictionary data.
        
        Args:
            data: Dictionary containing block data
            
        Returns:
            Block instance
        """
        block = cls(
            index=data["index"],
            events=data["events"],
            timestamp=data["timestamp"],
            previous_hash=data["previous_hash"],
            nonce=data.get("nonce", 0)
        )
        return block
    
    def __str__(self) -> str:
        """String representation of the block."""
        return f"Block(index={self.index}, events_count={len(self.events)}, hash={self.hash[:10]}...)"
    
    def __repr__(self) -> str:
        """Detailed string representation of the block."""
        return (f"Block(index={self.index}, events={len(self.events)}, "
                f"timestamp={self.timestamp}, hash={self.hash})")