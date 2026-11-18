"""
Cache policy for API key records and resolved permission decisions.
"""

import time
from typing import TYPE_CHECKING

from hierachain.adapters.database.auth_state import _key_digest

if TYPE_CHECKING:
    from hierachain.security.key_manager import KeyManager


class KeyCacheManager:
    """
    Manages caching of API keys and their permissions.
    Delegates cache lookups, checking expiration, and updates.
    """
    def __init__(self, key_manager: "KeyManager"):
        self.km = key_manager

    def get_key(self, api_key: str) -> dict | None:
        """
        Get key data from cache if valid.

        Args:
            api_key: The API key

        Returns:
            dict | None: Cached key data or None if not found/expired
        """
        cached = self.km.key_cache.get(_key_digest(api_key))
        if not cached:
            return None
        # Handle dict wrapper supporting manual expiration for tests
        if isinstance(cached, dict) and 'data' in cached:
            if self._is_expired(cached):
                return None
            return cached.get('data')
        return cached

    @staticmethod
    def _is_expired(cached: dict) -> bool:
        """Check if cached entry is expired."""
        cached_at = cached.get('cached_at')
        ttl = cached.get('ttl')
        if isinstance(cached_at, (int, float)) and isinstance(ttl, (int, float)):
            return time.time() - cached_at >= ttl
        return False

    def set_key(self, api_key: str, key_data: dict, ttl: int | None = None):
        """
        Cache API key data.

        Args:
            api_key: The API key to cache
            key_data: Key details
            ttl: TTL in seconds (optional)
        """
        ttl = ttl or self.km.cache_ttl
        self.km.key_cache.set(_key_digest(api_key), {
            'data': key_data,
            'cached_at': time.time(),
            'ttl': ttl
        }, ttl=ttl)

    def delete_key(self, api_key: str):
        """
        Remove API key from cache.

        Args:
            api_key: The API key to evict
        """
        if hasattr(self.km.key_cache, 'delete'):
            if self.km.key_cache.contains(_key_digest(api_key)):
                self.km.key_cache.delete(_key_digest(api_key))
        elif _key_digest(api_key) in self.km.key_cache:
            del self.km.key_cache[_key_digest(api_key)]

    def get_permission(self, api_key: str, resource: str) -> bool | None:
        """
        Get cached permission for resource.

        Args:
            api_key: The API key
            resource: The resource to check

        Returns:
            bool | None: The permission result or None
        """
        cache_key = f"{_key_digest(api_key)}:{resource}"
        return self.km.permission_cache.get(cache_key)

    def set_permission(self, api_key: str, resource: str, result: bool):
        """
        Cache permission check result.

        Args:
            api_key: The API key
            resource: The resource checked
            result: The boolean permission result
        """
        cache_key = f"{_key_digest(api_key)}:{resource}"
        self.km.permission_cache.set(cache_key, result, ttl=self.km.cache_ttl)

    def clear_permissions(self, api_key: str):
        """
        Clear all cached permissions for an API key.

        Args:
            api_key: The API key to clear permissions for
        """
        digest_prefix = f"{_key_digest(api_key)}:"
        keys_to_remove = [
            k for k in self.km.permission_cache.get_keys() if k.startswith(digest_prefix)
        ]
        for key in keys_to_remove:
            self.km.permission_cache.delete(key)
