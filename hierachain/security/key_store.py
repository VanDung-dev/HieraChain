"""
API key lookup over hashed in-memory or Redis-like backends.
"""

import json
from collections.abc import Iterator, MutableMapping
from typing import TYPE_CHECKING, Any

from hierachain.adapters.database.auth_state import _key_digest
from hierachain.security.secure_logging import SecureLogger
from hierachain.serialization import dumps_json, loads_json

if TYPE_CHECKING:
    from hierachain.security.key_manager import KeyManager

logger = SecureLogger("hierachain.security.key_store")


class HashedKeyStorage(MutableMapping[str, Any]):
    """Mapping view that only ever persists SHA-256 digests of API keys."""

    def __init__(self, backend: MutableMapping[str, Any] | None = None) -> None:
        self._backend: MutableMapping[str, Any] = backend if backend is not None else {}

    def __getitem__(self, key: str) -> Any:
        return self._backend[_key_digest(key)]

    def __setitem__(self, key: str, value: Any) -> None:
        self._backend[_key_digest(key)] = value

    def __delitem__(self, key: str) -> None:
        del self._backend[_key_digest(key)]

    def __iter__(self) -> Iterator[str]:
        return iter(self._backend)

    def __len__(self) -> int:
        return len(self._backend)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and _key_digest(key) in self._backend

    def get(self, key: object, default: Any = None) -> Any:
        if not isinstance(key, str):
            return default
        return self._backend.get(_key_digest(key), default)


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
            data = self.km.storage.get(f"api_key:{_key_digest(api_key)}")
            if isinstance(data, (str, bytes, bytearray)):
                return loads_json(data)
            return None
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("Error decoding key data from storage", error=str(e))
            return None
        # The Redis-like storage protocol does not define a shared error type.
        except Exception as e:  # noqa: BLE001
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
                self.km.storage.set(f"api_key:{_key_digest(api_key)}", dumps_json(data))
            # Keep the in-memory fallback for backend-specific storage errors.
            except Exception as e:  # noqa: BLE001
                logger.error("Error storing key to storage", error=str(e))
                # Fallback to memory
                self.km.storage[api_key] = data
        else:
            # Dict-like storage (in-memory fallback)
            self.km.storage[api_key] = data
