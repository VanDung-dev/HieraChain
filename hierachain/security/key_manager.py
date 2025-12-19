"""
Key Manager for API key storage, validation, and revocation checks.

This module handles API key management for the HieraChain framework,
ensuring secure access control without cryptocurrency concepts.
"""

import os
import time
import json
import hashlib
import binascii
import logging

logger = logging.getLogger(__name__)


class KeyManager:
    """
    Manages API keys for HieraChain framework access control.
    Handles key storage, validation, revocation checks, and permissions.
    """
    
    def __init__(self, storage_backend=None):
        """
        Initialize KeyManager with optional storage backend.
        
        Args:
            storage_backend: Optional storage backend (Redis, database, etc.)
        """
        self.storage = storage_backend or {}  # In-memory fallback
        self.revoked_keys: set[str] = set()
        self.key_cache: dict[str, dict] = {}
        self.cache_ttl = 300  # 5 minutes default TTL
        
    def is_valid(self, api_key: str) -> bool:
        """
        Check if API key is valid and properly formatted.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            bool: True if key is valid, False otherwise
        """
        if not api_key or len(api_key) < 16:
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
        
        Args:
            api_key: The API key to check
            resource: The resource/operation to check permission for
            
        Returns:
            bool: True if key has permission, False otherwise
        """
        key_data = self._get_key_data(api_key)
        if not key_data:
            return False
            
        permissions = key_data.get('permissions', [])
        
        # Check for wildcard permission or specific resource permission
        return 'all' in permissions or resource in permissions
    
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
    
    def cache_key(self, api_key: str, ttl: int = None):
        """
        Cache API key data for faster subsequent lookups.
        
        Args:
            api_key: The API key to cache
            ttl: Time to live in seconds (optional)
        """
        ttl = ttl or self.cache_ttl
        key_data = self._get_key_data(api_key)
        
        if key_data:
            self.key_cache[api_key] = {
                'data': key_data,
                'cached_at': time.time(),
                'ttl': ttl
            }
    
    def create_key(self, user_id: str, permissions: list, app_details: dict = None, expires_in: int = None) -> str:
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
        timestamp = str(int(time.time()))
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:8]
        random_suffix = hashlib.sha256(f"{timestamp}{user_id}".encode()).hexdigest()[:16]
        # Add random component to ensure keys are always different
        random_bytes = binascii.hexlify(os.urandom(8)).decode()[:8]
        api_key = f"hrc_{user_hash}_{random_suffix}_{random_bytes}"
        
        key_data = {
            'user_id': user_id,
            'permissions': permissions,
            'app_details': app_details or {},
            'created_at': time.time(),
            'expires_at': time.time() + expires_in if expires_in else None
        }
        
        self._store_key_data(api_key, key_data)
        
        return api_key
    
    def revoke_key(self, api_key: str):
        """
        Revoke an API key.
        
        Args:
            api_key: The API key to revoke
        """
        self.revoked_keys.add(api_key)
        # Remove from cache
        if api_key in self.key_cache:
            del self.key_cache[api_key]
    
    def _get_key_data(self, api_key: str) -> dict | None:
        """
        Get key data from cache or storage.
        
        Args:
            api_key: The API key
            
        Returns:
            dict | None: Key data or None if not found
        """
        # Check cache first
        cached = self.key_cache.get(api_key)
        if cached:
            if time.time() - cached['cached_at'] < cached['ttl']:
                return cached['data']
            else:
                # Cache expired
                del self.key_cache[api_key]
        
        # Get from storage
        # If it is dict, use the key directly, if it is Redis, use the prefix
        if hasattr(self.storage, 'set') and hasattr(self.storage, 'get'):
            # Redis-like storage
            try:
                data = self.storage.get(f"api_key:{api_key}")
                return json.loads(data) if data else None
            except Exception as e:
                logger.error(f"Error retrieving key from storage: {e}")
                return None
        else:
            # Dict-like storage (in-memory fallback)
            return self.storage.get(api_key)
    
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
                logger.error(f"Error storing key to storage: {e}")
                # Fallback to memory
                self.storage[api_key] = data
        else:
            # Dict-like storage (in-memory fallback)
            self.storage[api_key] = data


# Example usage and initialization
def initialize_default_keys():
    """Initialize some default API keys for testing and development."""
    key_manager = KeyManager()
    
    # Create demo keys
    demo_key = key_manager.create_key(
        user_id="demo_user",
        permissions=["events", "chains", "proofs"],
        app_details={"name": "Demo Application", "version": "1.0"}
    )
    
    admin_key = key_manager.create_key(
        user_id="admin_user", 
        permissions=["all"],
        app_details={"name": "Admin Console", "version": "1.0"}
    )
    
    return {
        "demo_key": demo_key,
        "admin_key": admin_key,
        "key_manager": key_manager
    }
