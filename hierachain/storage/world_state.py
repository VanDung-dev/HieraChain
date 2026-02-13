"""
World State Management Module

This module implements a simplified world state mechanism adapted for the hierarchical 
blockchain structure. The world state represents the current values of all ledger states, 
enabling efficient read/write operations without traversing the entire blockchain.

The world state is updated through events processed from blocks, maintaining entity states
with efficient indexing for common query patterns.
"""

from typing import Any
from hierachain.storage.memory_storage import MemoryStorage


def _extract_events(block) -> list:
    """Extract events from block, handling different block formats."""
    if hasattr(block, 'to_event_list'):
        return block.to_event_list()
    if hasattr(block, 'events'):
        return block.events
    return block.get('events', [])


class WorldState:
    """Simplified World State mechanism for HieraChain"""
    
    # Event handlers mapping
    _EVENT_HANDLERS = {
        "creation": lambda event: {
            "created_at": event["timestamp"],
            "status": "active"
        },
        "update": lambda event: event.get("updates", {}),
        "status_change": lambda event: {"status": event["new_status"]},
    }
    
    def __init__(self, chain_name: str, storage_backend=None):
        """
        chain_name: Chain name
        storage_backend: Optional storage backend (Redis, Memory, etc.)
        """
        self.chain_name = chain_name
        self.storage = storage_backend or MemoryStorage()
        self.state_cache = {}
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Set up indexes for frequent queries"""
        self.storage.create_index("entity_id")
        self.storage.create_index("timestamp")

    def _apply_event_to_state(self, current_state: dict, event: dict) -> dict:
        """Apply a single event to the current state."""
        event_type = event.get("event")
        handler = self._EVENT_HANDLERS.get(event_type)
        
        if handler:
            current_state.update(handler(event))
        
        current_state["last_updated"] = event["timestamp"]
        return current_state
    
    def update_from_block(self, block):
        """Update world state from new block"""
        events = _extract_events(block)
        
        for event in events:
            if "entity_id" not in event:
                continue
            
            entity_key = f"{self.chain_name}:{event['entity_id']}"
            current_state = self.storage.get(entity_key) or {}
            current_state = self._apply_event_to_state(current_state, event)
            
            self.storage.set(entity_key, current_state)
            self.state_cache[entity_key] = current_state
    
    def get_entity_state(self, entity_id: str) -> dict[str, Any] | None:
        """Get current state of entity"""
        entity_key = f"{self.chain_name}:{entity_id}"
        if entity_key in self.state_cache:
            return self.state_cache[entity_key]
            
        state = self.storage.get(entity_key)
        if state:
            self.state_cache[entity_key] = state
        return state
    
    def query_by_index(self, index_name: str, value: Any):
        """Query using index"""
        return self.storage.query_by_index(index_name, value)