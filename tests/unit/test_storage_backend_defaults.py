"""Tests for the default storage backend and PostgreSQL fallback."""

from hierachain.adapters.database.postgres_adapter import PostgresAdapter
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter
from hierachain.config.settings import ProductionSettings, Settings, settings
from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager


def test_development_storage_defaults_to_postgres(monkeypatch):
    monkeypatch.delenv("HRC_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HRC_DATABASE_URL", raising=False)

    assert Settings().STORAGE_BACKEND == "postgres"
    assert Settings.DEFAULT_STORAGE_BACKEND == "postgres"
    assert ProductionSettings.DEFAULT_STORAGE_BACKEND == "postgres"


def test_postgres_failure_falls_back_to_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "postgres")
    monkeypatch.setattr(PostgresAdapter, "_init_pool", lambda self: None)
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        f"sqlite:///{tmp_path / 'fallback.db'}",
    )

    storage = HierarchyManager._create_storage()

    assert isinstance(storage, SQLiteAdapter)
    assert storage.database_path == str(tmp_path / "fallback.db")
    storage.close()
