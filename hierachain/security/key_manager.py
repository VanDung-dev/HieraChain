"""
Key Manager for API key storage, validation, and revocation checks.

This module handles API key management for the HieraChain Ledger,
ensuring secure access control without cryptocurrency concepts.
"""

import os
import warnings
from collections.abc import MutableMapping
from typing import Any

from hierachain.adapters.database.auth_state import (
    RedisRevocationStore,
    SQLiteRevocationStore,
    _key_digest,
)
from hierachain.core.cache import AdvancedCache
from hierachain.security.key_cache import KeyCacheManager
from hierachain.security.key_records import (
    build_key_record,
    generate_api_key,
    has_valid_permissions,
    key_is_expired,
    key_prefix,
)
from hierachain.security.key_revocation import RevocationPolicy
from hierachain.security.key_store import HashedKeyStorage, KeyStorage
from hierachain.security.secure_logging import SecureLogger

logger = SecureLogger("hierachain.security.key_manager")


class KeyManager:
    """
    Manages API keys for HieraChain Ledger access control.
    Handles key storage, validation, revocation checks, and permissions.
    """

    def __init__(
        self,
        storage_backend: Any | None = None,
        config: dict | None = None,
        revocation_store: SQLiteRevocationStore | RedisRevocationStore | None = None,
    ) -> None:
        """
        Initialize KeyManager with optional storage backend.

        Args:
            storage_backend: Optional storage backend (Redis, database, etc.)
            config: Optional configuration dict with security settings.
                    - verify_signatures: bool, default True.
                      Set to False for testing only!
        """
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

        self.storage: Any
        if storage_backend is None:
            self.storage = HashedKeyStorage()
        elif isinstance(storage_backend, HashedKeyStorage):
            self.storage = storage_backend
        elif isinstance(storage_backend, MutableMapping):
            self.storage = HashedKeyStorage({
                _key_digest(api_key): key_data
                for api_key, key_data in storage_backend.items()
            })
        else:
            self.storage = storage_backend
        self.revoked_keys: set[str] = set()
        if revocation_store is None:
            from hierachain.config.settings import get_settings
            revocation_store = SQLiteRevocationStore(
                get_settings().API_KEY_REVOCATIONS_DB
            )
        self.revocation_store = revocation_store
        self.key_cache = AdvancedCache(max_size=5000, eviction_policy="ttl")
        self.permission_cache = AdvancedCache(max_size=10000, eviction_policy="lru")
        self.cache_ttl = 300  # 5 minutes default TTL

        self._revocation_policy = RevocationPolicy(self.revoked_keys, revocation_store)
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

        key_data = self._get_key_data(api_key)
        if not key_data:
            return False

        return not key_is_expired(key_data)

    def is_revoked(self, api_key: str) -> bool:
        """
        Check if API key has been revoked.

        Args:
            api_key: The API key to check

        Returns:
            bool: True if key is revoked, False otherwise
        """
        return self._revocation_policy.is_revoked(api_key)

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

        permissions = key_data.get("permissions", [])
        if not has_valid_permissions(key_data):
            return False

        # Check for wildcard permission or specific resource permission
        result = "all" in permissions or resource in permissions

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

    def get_permissions(self, api_key: str) -> list[str]:
        """Return the permissions assigned to an API key."""
        key_data = self._get_key_data(api_key)
        permissions = key_data.get('permissions', []) if key_data else []
        return permissions.copy() if key_data and has_valid_permissions(key_data) else []

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
        permissions: list[str],
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
        if not isinstance(permissions, list) or not all(isinstance(permission, str) for permission in permissions):
            raise ValueError("permissions must be a list of strings")

        api_key = generate_api_key(user_id)
        key_data = build_key_record(user_id, permissions, app_details, expires_in)
        self._storage_helper.set(api_key, key_data)

        logger.security_event(
            event_type="api_key_created",
            message="New API key created",
            severity="medium",
            user_id=user_id,
            permissions=permissions,
        )

        return api_key

    def revoke_key(self, api_key: str) -> None:
        """
        Revoke an API key.

        Args:
            api_key: The API key to revoke
        """
        self._revocation_policy.revoke(api_key)

        # Clear caches
        self._cache_helper.delete_key(api_key)
        self._cache_helper.clear_permissions(api_key)

        logger.security_event(
            event_type="api_key_revoked",
            message="API key revoked",
            severity="high",
            key_prefix=key_prefix(api_key),
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
            if isinstance(cached_data, dict) and has_valid_permissions(cached_data):
                return cached_data
            return None

        # Get from storage
        key_data = self._storage_helper.get(api_key)
        if not isinstance(key_data, dict) or not has_valid_permissions(key_data):
            return None
        return key_data


# Example usage and initialization
def initialize_default_keys():
    """Initialize some default API keys for testing and development only."""
    import sys

    from hierachain.config.settings import Settings

    if (
        os.environ.get("PYTEST_CURRENT_TEST") is None
        and "pytest" not in sys.modules
        and Settings().env == "production"
    ):
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
