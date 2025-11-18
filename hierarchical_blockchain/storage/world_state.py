"""
World State Management Module

This module implements a simplified world state mechanism adapted for the hierarchical 
blockchain structure. The world state represents the current values of all ledger states, 
enabling efficient read/write operations without traversing the entire blockchain.

The world state is updated through events processed from blocks, maintaining entity states
with efficient indexing for common query patterns.
"""

from typing import Dict, Any, Optional
from hierarchical_blockchain.storage.memory_storage import MemoryStorage


class WorldState:
    """Simplified World State mechanism for hierarchical blockchain"""
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
    
    def update_from_block(self, block):
        """Update world state from new block"""
        for event in block.events:
            if "entity_id" in event:
                entity_key = f"{self.chain_name}:{event['entity_id']}"
                current_state = self.storage.get(entity_key) or {}
                
                # Update state based on event type
                if event["event"] == "creation":
                    current_state.update({
                        "created_at": event["timestamp"],
                        "status": "active"
                    })
                elif event["event"] == "update":
                    current_state.update(event.get("updates", {}))
                elif event["event"] == "status_change":
                    current_state["status"] = event["new_status"]
                
                current_state["last_updated"] = event["timestamp"]
                self.storage.set(entity_key, current_state)
                self.state_cache[entity_key] = current_state
    
    def get_entity_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
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