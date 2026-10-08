"""
Database adapters for blockchain data persistence.
"""

from importlib import import_module

__all__ = ["PostgresAdapter", "PostgresAuditManifest", "RedisStorageAdapter", "SQLBase", "SQLiteAdapter"]

_MODULES = {
    "PostgresAdapter": "postgres_adapter",
    "PostgresAuditManifest": "audit_manifest",
    "RedisStorageAdapter": "redis_adapter",
    "SQLBase": "base.sql_adapter",
    "SQLiteAdapter": "sqlite_adapter",
}


def __getattr__(name: str) -> type:
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
