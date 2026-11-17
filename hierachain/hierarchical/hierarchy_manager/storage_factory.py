from __future__ import annotations

from typing import Any

from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.config.settings import settings


def create_storage_backend() -> Any | None:
    backend = getattr(settings, "STORAGE_BACKEND", settings.DEFAULT_STORAGE_BACKEND)

    def create_sqlite_storage() -> SQLiteAdapter:
        db_path = "hierachain.db"
        if settings.DATABASE_URL.startswith("sqlite:///"):
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        return SQLiteAdapter(database_path=db_path)

    if backend == "sqlite":
        return create_sqlite_storage()

    if backend in ("postgres", "postgresql"):
        postgres = None
        try:
            from hierachain.adapters.database.postgres_adapter import PostgresAdapter

            postgres = PostgresAdapter(database_url=settings.DATABASE_URL)
            with postgres._get_connection() as connection:
                connection.cursor().execute("SELECT 1 FROM chains LIMIT 0")
            return postgres
        except Exception as exc:
            if postgres is not None:
                postgres.close()
            raise RuntimeError("Configured PostgreSQL storage is unavailable") from exc

    if backend == "redis":
        from hierachain.adapters.database.redis_ledger import RedisLedgerAdapter

        return RedisLedgerAdapter()

    if backend == "memory":
        return None
    raise ValueError(f"Unsupported HRC_STORAGE_BACKEND value: {backend!r}")
