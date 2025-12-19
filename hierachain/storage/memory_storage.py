"""
Memory Storage Module for HieraChain

This module provides an in-memory storage implementation for the HieraChain system.
It supports key-value storage with indexing capabilities for efficient data retrieval.
"""

from typing import   Any, Optional


class MemoryStorage:
    """Simple in-memory storage backend for HieraChain"""
    
    def __init__(self):
        self.data: dict[str, dict[str, Any]] = {}
        self.indexes: dict[str, dict[Any, list[str]]] = {}
    
    def create_index(self, field_name: str):
        """Create index for field"""
        if field_name not in self.indexes:
            self.indexes[field_name] = {}
    
    def get(self, key: str) -> Optional[dict[str, Any]]:
        """Get value by key"""
        return self.data.get(key)
    
    def set(self, key: str, value: dict[str, Any]):
        """Set value by key"""
        self.data[key] = value
        
        # Update indexes
        for field_name in self.indexes:
            if field_name in value:
                field_value = value[field_name]
                if field_value not in self.indexes[field_name]:
                    self.indexes[field_name][field_value] = []
                if key not in self.indexes[field_name][field_value]:
                    self.indexes[field_name][field_value].append(key)
    
    def delete(self, key: str) -> bool:
        """Delete value by key"""
        if key in self.data:
            # Remove from indexes
            value = self.data[key]
            for field_name in self.indexes:
                if field_name in value:
                    field_value = value[field_name]
                    if field_value in self.indexes[field_name]:
                        if key in self.indexes[field_name][field_value]:
                            self.indexes[field_name][field_value].remove(key)
                        if not self.indexes[field_name][field_value]:
                            del self.indexes[field_name][field_value]
            
            del self.data[key]
            return True
        return False
    
    def query_by_index(self, index_name: str, value: Any) -> list[str]:
        """Query using index"""
        if index_name not in self.indexes:
            return []
        return self.indexes[index_name].get(value, [])
    
    def get_all_keys(self) -> list[str]:
        """Get all keys in storage"""
        return list(self.data.keys())
    
    def get_all_values(self) -> list[dict[str, Any]]:
        """Get all values in storage"""
        return list(self.data.values())
    
    def clear(self):
        """Clear all data and indexes"""
        self.data.clear()
        self.indexes.clear()
    
    def size(self) -> int:
        """Get number of items in storage"""
        return len(self.data)