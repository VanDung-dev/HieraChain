"""
Key Manager for API key storage, validation, and revocation checks.

This module handles API key management for the HieraChain Ledger,
ensuring secure access control without cryptocurrency concepts.
"""

import os
import time
import orjson
import hashlib
import secrets

from hierachain.core.cache import AdvancedCache
from hierachain.security.secure_logging import SecureLogger

logger = SecureLogger("hierachain.security.key_manager")


class KeyStorage:
    """
    Handles API key storage operations.
    Supports both Redis-like (with set/get methods) and dict-like storage backends.
    """
    def __init__(self, key_manager: "KeyManager"):
        self.km = key_manager

    def get(self, api_key: str) -> dict | None:
        """
        Get key data from storage.
        
        Args:
            api_key: The API key to retrieve
            
        Returns:
            dict | None: The key data, or None if not found
        """
        # Check if Redis-like storage (has set/get methods)
        if not (hasattr(self.km.storage, 'set') and hasattr(self.km.storage, 'get')):
            # Dict-like storage (in-memory fallback)
            return self.km.storage.get(api_key)
        
        # Redis-like storage
        try:
            data = self.km.storage.get(f"api_key:{api_key}")
            if isinstance(data, (str, bytes, bytearray)):
                return orjson.loads(data)
            return None
        except (orjson.JSONDecodeError, TypeError) as e:
            logger.error("Error decoding key data from storage", error=str(e))
            return None
        except Exception as e:
            logger.error("Error retrieving key from storage", error=str(e))
            return None

    def set(self, api_key: str, data: dict):
        """
        Store key data in storage.
        
        Args:
            api_key: The API key
            data: Key data to store
        """
        if hasattr(self.km.storage, 'set') and hasattr(self.km.storage, 'get'):
            # Redis-like storage
            try:
                self.km.storage.set(f"api_key:{api_key}", orjson.dumps(data).decode())
            except Exception as e:
                logger.error("Error storing key to storage", error=str(e))
                # Fallback to memory
                self.km.storage[api_key] = data
        else:
            # Dict-like storage (in-memory fallback)
            self.km.storage[api_key] = data


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
        cached = self.km.key_cache.get(api_key)
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
        self.km.key_cache.set(api_key, {
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
            if self.km.key_cache.contains(api_key):
                self.km.key_cache.delete(api_key)
        elif api_key in self.km.key_cache:
            del self.km.key_cache[api_key]

    def get_permission(self, api_key: str, resource: str) -> bool | None:
        """
        Get cached permission for resource.
        
        Args:
            api_key: The API key
            resource: The resource to check
            
        Returns:
            bool | None: The permission result or None
        """
        cache_key = f"{api_key}:{resource}"
        return self.km.permission_cache.get(cache_key)

    def set_permission(self, api_key: str, resource: str, result: bool):
        """
        Cache permission check result.
        
        Args:
            api_key: The API key
            resource: The resource checked
            result: The boolean permission result
        """
        cache_key = f"{api_key}:{resource}"
        self.km.permission_cache.set(cache_key, result, ttl=self.km.cache_ttl)

    def clear_permissions(self, api_key: str):
        """
        Clear all cached permissions for an API key.
        
        Args:
            api_key: The API key to clear permissions for
        """
        keys_to_remove = [
            k for k in self.km.permission_cache.get_keys() if k.startswith(f"{api_key}:")
        ]
        for key in keys_to_remove:
            self.km.permission_cache.delete(key)


class KeyManager:
    """
    Manages API keys for HieraChain Ledger access control.
    Handles key storage, validation, revocation checks, and permissions.
    """
    
    def __init__(self, storage_backend=None, config=None):
        """
        Initialize KeyManager with optional storage backend.
        
        Args:
            storage_backend: Optional storage backend (Redis, database, etc.)
            config: Optional configuration dict with security settings.
                    - verify_signatures: bool, default True.
                      Set to False for testing only!
        """
        import warnings
        
        if config is None:
            config = {}
        
        if not config.get("verify_signatures", True):
            from hierachain.config.settings import settings
            if settings.env in ("product", "production"):
                raise RuntimeError("Security Exception: verify_signatures cannot be disabled in production mode!")
            warnings.warn(
                "Security: verify_signatures=False is insecure! Use only for testing!",
                category=UserWarning
            )
        
        self.storage = storage_backend or {}  # In-memory fallback
        self.revoked_keys: set[str] = set()
        self.key_cache = AdvancedCache(max_size=5000, eviction_policy="ttl")
        self.permission_cache = AdvancedCache(max_size=10000, eviction_policy="lru")
        self.cache_ttl = 300  # 5 minutes default TTL

        # Helpers
        self._storage_helper = KeyStorage(self)
        self._cache_helper = KeyCacheManager(self)
        
    def is_valid(self, api_key: str | None) -> bool:
        """
        Check if API key is valid and properly formatted.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            bool: True if key is valid, False otherwise
        """
        if not api_key or len(api_key) < 16 or self.is_revoked(api_key):
            return False

        # Check if key exists in storage
        key_data = self._get_key_data(api_key)
        if not key_data:
            return False
            
        # Check expiration
        expires_at = key_data.get('expires_at')
        if expires_at is None:
            return True
        if isinstance(expires_at, (int, float)):
            return time.time() <= float(expires_at)
        return False
    
    def is_revoked(self, api_key: str) -> bool:
        """
        Check if API key has been revoked.
        
        Args:
            api_key: The API key to check
            
        Returns:
            bool: True if key is revoked, False otherwise
        """
        return api_key in self.revoked_keys
    
    def has_permission(self, api_key: str, resource: str) -> bool:
        """
        Check if API key has permission for specific resource.
        Uses permission cache for performance optimization.
        
        Args:
            api_key: The API key to check
            resource: The resource/operation to check permission for
            
        Returns:
            bool: True if key has permission, False otherwise
        """
        if self.is_revoked(api_key):
            return False

        # Check permission cache first
        cached = self._cache_helper.get_permission(api_key, resource)
        if cached is not None:
            return cached
        
        # Get key data if not in cache
        key_data = self._get_key_data(api_key)
        if not key_data:
            # Cache negative result
            self._cache_helper.set_permission(api_key, resource, False)
            return False
            
        permissions = key_data.get('permissions', [])
        
        # Check for wildcard permission or specific resource permission
        result = 'all' in permissions or resource in permissions
        
        # Cache the result for efficiency
        self._cache_helper.set_permission(api_key, resource, result)
        
        return result
    
    def get_user(self, api_key: str) -> str | None:
        """
        Get user ID associated with API key.
        
        Args:
            api_key: The API key
            
        Returns:
            str | None: User ID or None if not found
        """
        key_data = self._get_key_data(api_key)
        return key_data.get('user_id') if key_data else None
    
    def get_app_details(self, api_key: str) -> dict | None:
        """
        Get application details associated with API key.
        
        Args:
            api_key: The API key
            
        Returns:
            dict | None: App details or None if not found
        """
        key_data = self._get_key_data(api_key)
        return key_data.get('app_details', {}) if key_data else None
    
    def cache_key(self, api_key: str, ttl: int | None = None):
        """
        Cache API key data for faster subsequent lookups.
        
        Args:
            api_key: The API key to cache
            ttl: Time to live in seconds (optional)
        """
        key_data = self._get_key_data(api_key)
        if key_data:
            self._cache_helper.set_key(api_key, key_data, ttl)
    
    def create_key(
        self,
        user_id: str,
        permissions: list,
        app_details: dict | None = None,
        expires_in: int | None = None
    ) -> str:
        """
        Create a new API key for a user.
        
        Args:
            user_id: User identifier
            permissions: List of permissions for this key
            app_details: Application details (optional)
            expires_in: Expiration time in seconds from now (optional)
            
        Returns:
            str: Generated API key
        """
        # Generate secure API key
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:8]
        random_component = secrets.token_urlsafe(32)
        api_key = f"hrc_{user_hash}_{random_component}"
        
        key_data = {
            'user_id': user_id,
            'permissions': permissions,
            'app_details': app_details or {},
            'created_at': time.time(),
            'expires_at': time.time() + expires_in if expires_in else None
        }
        
        self._storage_helper.set(api_key, key_data)

        logger.security_event(
            event_type="api_key_created",
            message="New API key created",
            severity="medium",
            user_id=user_id,
            permissions=permissions,
        )

        return api_key
    
    def revoke_key(self, api_key: str):
        """
        Revoke an API key.
        
        Args:
            api_key: The API key to revoke
        """
        self.revoked_keys.add(api_key)
        
        # Clear caches
        self._cache_helper.delete_key(api_key)
        self._cache_helper.clear_permissions(api_key)

        key_prefix = api_key[:8] if len(api_key) >= 8 else "short"
        logger.security_event(
            event_type="api_key_revoked",
            message="API key revoked",
            severity="high",
            key_prefix=key_prefix,
        )
    
    def _get_key_data(self, api_key: str) -> dict | None:
        """
        Get key data from cache or storage.
        
        Args:
            api_key: The API key
            
        Returns:
            dict | None: Key data or None if not found
        """
        # Check cache first
        cached_data = self._cache_helper.get_key(api_key)
        if cached_data is not None:
            return cached_data
        
        # Get from storage
        return self._storage_helper.get(api_key)


# Example usage and initialization
def initialize_default_keys():
    """Initialize some default API keys for testing and development only."""
    if os.environ.get("HRC_ENV", "dev").lower() in ["production", "prod", "product"]:
        logger.critical("Attempted to create default API keys in production environment!")
        raise RuntimeError("Default keys cannot be created in production environment")
        
    key_manager = KeyManager()
    
    # Create demo keys for development only
    demo_key = key_manager.create_key(
        user_id="demo_user",
        permissions=["events", "chains", "proofs"],
        app_details={"name": "Demo Application", "version": "1.0", "environment": "development"}
    )
    
    admin_key = key_manager.create_key(
        user_id="admin_user",
        permissions=["all"],
        app_details={"name": "Admin Console", "version": "1.0", "environment": "development"}
    )
    
    logger.warning("Default development API keys created. This should NEVER happen in production!")
    
    return {
        "demo_key": demo_key,
        "admin_key": admin_key,
        "key_manager": key_manager
    }
