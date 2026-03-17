"""
Memory Storage Module for HieraChain

This module provides an in-memory storage implementation for the HieraChain system.
It supports key-value storage with indexing capabilities for efficient data retrieval.
"""

from typing import Any


def _remove_key_from_single_index(
    index: dict[Any, list[str]], field_value: Any, key: str
) -> None:
    """Remove a key from a single index value entry."""
    if field_value not in index:
        return

    keys = index[field_value]
    if key not in keys:
        return

    keys.remove(key)
    if not keys:
        del index[field_value]


class MemoryStorage:
    """Simple in-memory storage backend for HieraChain"""
    
    def __init__(self):
        self.data: dict[str, dict[str, Any]] = {}
        self.indexes: dict[str, dict[Any, list[str]]] = {}
    
    def create_index(self, field_name: str):
        """Create index for field"""
        if field_name not in self.indexes:
            self.indexes[field_name] = {}
    
    def get(self, key: str) -> dict[str, Any] | None:
        """Get value by key"""
        return self.data.get(key)
    
    def _update_index_for_key(self, key: str, value: dict[str, Any]) -> None:
        """Update all indexes for a given key-value pair."""
        for field_name, index in self.indexes.items():
            if field_name in value:
                field_value = value[field_name]
                keys = index.setdefault(field_value, [])
                if key not in keys:
                    keys.append(key)

    def _remove_from_index(self, key: str, value: dict[str, Any]):
        """Remove key from all indexes."""
        for field_name, index in self.indexes.items():
            if field_name in value:
                _remove_key_from_single_index(index, value[field_name], key)
    
    def set(self, key: str, value: dict[str, Any]):
        """Set value by key"""
        self.data[key] = value
        self._update_index_for_key(key, value)
    
    def delete(self, key: str) -> bool:
        """Delete value by key"""
        if key not in self.data:
            return False
        
        value = self.data.pop(key)
        self._remove_from_index(key, value)
        return True
    
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
    
    def clear(self) -> None:
        """Clear all data and indexes"""
        self.data.clear()
        self.indexes.clear()
    
    def size(self) -> int:
        """Get number of items in storage"""
        return len(self.data)
