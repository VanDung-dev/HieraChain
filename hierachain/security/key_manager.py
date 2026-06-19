"""
Key Manager for API key storage, validation, and revocation checks.

This module handles API key management for the HieraChain Ledger,
ensuring secure access control without cryptocurrency concepts.
"""

import os
import time
import json
import hashlib
import secrets

from hierachain.core.cache import AdvancedCache
from hierachain.security.secure_logging import SecureLogger

logger = SecureLogger("hierachain.security.key_manager")


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
                    - Verify_signatures: bool, default True.
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
        
    def is_valid(self, api_key: str | None) -> bool:
        """
        Check if API key is valid and properly formatted.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            bool: True if key is valid, False otherwise
        """
        if not api_key or len(api_key) < 16:
            return False
            
        if self.is_revoked(api_key):
            return False

        # Check if key exists in storage
        key_data = self._get_key_data(api_key)
        if not key_data:
            return False
            
        # Check expiration
        if key_data.get('expires_at') and time.time() > key_data['expires_at']:
            return False
            
        return True
    
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

        cache_key = f"{api_key}:{resource}"
        
        # Check permission cache first - optimized with AdvancedCache
        cached = self.permission_cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Get key data if not in cache
        key_data = self._get_key_data(api_key)
        if not key_data:
            # Cache negative result
            self.permission_cache.set(cache_key, False, ttl=self.cache_ttl)
            return False
            
        permissions = key_data.get('permissions', [])
        
        # Check for wildcard permission or specific resource permission
        result = 'all' in permissions or resource in permissions
        
        # Cache the result for efficiency
        self.permission_cache.set(cache_key, result, ttl=self.cache_ttl)
        
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
        ttl = ttl or self.cache_ttl
        key_data = self._get_key_data(api_key)
        
        if key_data:
            self.key_cache.set(api_key, {
                'data': key_data,
                'cached_at': time.time(),
                'ttl': ttl
            }, ttl=ttl)
    
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
        
        self._store_key_data(api_key, key_data)

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
        # Remove from cache safely supporting both AdvancedCache and raw dict
        if hasattr(self.key_cache, 'delete'):
            if self.key_cache.contains(api_key):
                self.key_cache.delete(api_key)
        elif api_key in self.key_cache:
            del self.key_cache[api_key]
        
        # Clear permission cache for this key
        keys_to_remove = [
            k for k in self.permission_cache.get_keys() if k.startswith(f"{api_key}:")
        ]
        for key in keys_to_remove:
            self.permission_cache.delete(key)

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
        cached_data = self._get_from_cache(api_key)
        if cached_data is not None:
            return cached_data
        
        # Get from storage
        return self._get_from_storage(api_key)
    
    def _get_from_cache(self, api_key: str) -> dict | None:
        """
        Get key data from cache if valid.
        
        Args:
            api_key: The API key
            
        Returns:
            dict | None: Cached key data or None if not found/expired
        """
        cached = self.key_cache.get(api_key)
        if not cached:
            return None
        # Handle dict wrapper supporting manual expiration for tests
        if isinstance(cached, dict) and 'data' in cached:
            cached_at = cached.get('cached_at')
            ttl = cached.get('ttl')
            if isinstance(cached_at, (int, float)) and isinstance(ttl, (int, float)):
                if time.time() - cached_at >= ttl:
                    return None
            return cached.get('data')
        return cached
    
    def _get_from_storage(self, api_key: str) -> dict | None:
        """
        Get key data from storage backend.
        
        Args:
            api_key: The API key
            
        Returns:
            dict | None: Key data or None if not found
        """
        # Check if Redis-like storage (has set/get methods)
        if not (hasattr(self.storage, 'set') and hasattr(self.storage, 'get')):
            # Dict-like storage (in-memory fallback)
            return self.storage.get(api_key)
        
        # Redis-like storage
        try:
            data = self.storage.get(f"api_key:{api_key}")
            if isinstance(data, (str, bytes, bytearray)):
                return json.loads(data)
            return None
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Error decoding key data from storage", error=str(e))
            return None
        except Exception as e:
            logger.error("Error retrieving key from storage", error=str(e),)
            return None
    
    def _store_key_data(self, api_key: str, data: dict):
        """
        Store key data in storage.
        
        Args:
            api_key: The API key
            data: Key data to store
        """
        # If it is dict, use the key directly, if it is Redis, use the prefix
        if hasattr(self.storage, 'set') and hasattr(self.storage, 'get'):
            # Redis-like storage
            try:
                self.storage.set(f"api_key:{api_key}", json.dumps(data))
            except Exception as e:
                logger.error("Error storing key to storage", error=str(e))
                # Fallback to memory
                self.storage[api_key] = data
        else:
            # Dict-like storage (in-memory fallback)
            self.storage[api_key] = data


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
