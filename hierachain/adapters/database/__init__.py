"""
Database adapters for blockchain data persistence.
"""

from importlib import import_module

__all__ = [
    "LedgerStorage", "PostgresAdapter", "RedisLedgerAdapter", "RedisStorageAdapter", "SQLBase", "SQLiteAdapter",
]

_MODULES = {
    "LedgerStorage": "contract",
    "PostgresAdapter": "postgres_adapter",
    "RedisStorageAdapter": "redis_adapter",
    "RedisLedgerAdapter": "redis_ledger",
    "SQLBase": "base.sql_adapter",
    "SQLiteAdapter": "sqlite_adapter",
}


def __getattr__(name: str) -> type:
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
