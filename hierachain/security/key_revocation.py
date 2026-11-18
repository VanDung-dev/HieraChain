"""
Revocation checks over an in-memory set plus an optional durable store.
"""

from collections.abc import MutableSet
from typing import Any


class RevocationPolicy:
    def __init__(self, revoked_keys: MutableSet[str], store: Any | None = None) -> None:
        self.revoked_keys = revoked_keys
        self.store = store

    def is_revoked(self, api_key: str) -> bool:
        return api_key in self.revoked_keys or (
            self.store is not None and self.store.is_revoked(api_key)
        )

    def revoke(self, api_key: str) -> None:
        if self.store is not None:
            self.store.revoke(api_key)
        self.revoked_keys.add(api_key)
