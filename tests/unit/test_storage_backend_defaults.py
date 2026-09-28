"""Tests for the default storage backend and PostgreSQL fallback."""

import os
import subprocess
import sys

import pytest

from hierachain.adapters.database.postgres_adapter import PostgresAdapter
from hierachain.config.settings import ProductionSettings, Settings
from hierachain.hierarchical.hierarchy_manager.base import HierarchyManager


def test_blank_primary_database_url_uses_hrc_alias() -> None:
    database_url = "postgresql://example.invalid:5432/hierachain"
    env = {
        **os.environ,
        "HRC_ENV": "prod",
        "HRC_AUTH_ENABLED": "true",
        "HRC_STORAGE_BACKEND": "postgres",
        "DATABASE_URL": "  ",
        "HRC_DATABASE_URL": database_url,
    }
    code = (
        "from hierachain.config.settings import settings; "
        f"assert settings.DATABASE_URL == {database_url!r}; "
        "assert settings.STORAGE_BACKEND == 'postgres'"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


def test_development_storage_defaults_to_postgres(monkeypatch):
    monkeypatch.delenv("HRC_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HRC_DATABASE_URL", raising=False)

    assert Settings().STORAGE_BACKEND == "postgres"
    assert Settings.DEFAULT_STORAGE_BACKEND == "postgres"
    assert ProductionSettings.DEFAULT_STORAGE_BACKEND == "postgres"


def test_postgres_failure_does_not_fall_back_to_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "postgres")
    monkeypatch.setattr(PostgresAdapter, "_init_pool", lambda self: None)

    with pytest.raises(RuntimeError, match="Configured PostgreSQL storage is unavailable"):
        HierarchyManager._create_storage()


def test_invalid_storage_backend_does_not_disable_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "postgres_typo")

    with pytest.raises(ValueError, match="Unsupported HRC_STORAGE_BACKEND value"):
        HierarchyManager._create_storage()


def test_explicit_memory_backend_remains_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "memory")

    assert HierarchyManager._create_storage() is None
