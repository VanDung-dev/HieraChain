"""
Key record shape and expiry rules for the HieraChain API key manager.
"""

import hashlib
import secrets
import time
from typing import Any


def has_valid_permissions(key_data: dict[str, Any]) -> bool:
    permissions = key_data.get("permissions", [])
    return isinstance(permissions, list) and all(
        isinstance(permission, str) for permission in permissions
    )


def key_is_expired(key_data: dict[str, Any], now: float | None = None) -> bool:
    expires_at = key_data.get("expires_at")
    if expires_at is None:
        return False
    if isinstance(expires_at, (int, float)):
        return (time.time() if now is None else now) > float(expires_at)
    return True


def generate_api_key(user_id: str) -> str:
    user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:8]
    random_component = secrets.token_urlsafe(32)
    return f"hrc_{user_hash}_{random_component}"


def build_key_record(
    user_id: str,
    permissions: list[str],
    app_details: dict | None = None,
    expires_in: int | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    created_at = time.time() if now is None else now
    return {
        "user_id": user_id,
        "permissions": permissions,
        "app_details": app_details or {},
        "created_at": created_at,
        "expires_at": created_at + expires_in if expires_in else None,
    }


def key_prefix(api_key: str) -> str:
    return api_key[:8] if len(api_key) >= 8 else "short"
