"""Regression coverage for durable hierarchy and node CLI behavior."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner

from hierachain.cli import hrc
from hierachain.cli import node as node_cli
from hierachain.cli import store as cli_store
from hierachain.config.settings import get_settings, settings


class _FakeStorage:
    def close(self) -> None:
        return


class _FakeChain:
    def __init__(self, name: str, domain_type: str) -> None:
        self.name = name
        self.domain_type = domain_type
        self.chain: list[SimpleNamespace] = []
        self.shutdown = Mock()

    def add_event(self, event: dict[str, Any]) -> str:
        self.chain.append(SimpleNamespace(events=[event.copy()]))
        return "synthetic-event-id"


class _FakeHierarchyManager:
    chains: dict[str, _FakeChain] = {}
    fail_create = False

    def __init__(self) -> None:
        self.storage = _FakeStorage()
        self.transaction_manager = SimpleNamespace(journal=Mock())
        self.create_calls: list[tuple[str, str]] = []

    def get_sub_chain(self, name: str) -> _FakeChain | None:
        return self.chains.get(name)

    def get_all_sub_chains(self) -> dict[str, _FakeChain]:
        return self.chains

    def create_sub_chain(self, name: str, domain_type: str) -> bool:
        self.create_calls.append((name, domain_type))
        if self.fail_create:
            raise RuntimeError("synthetic storage failure")
        if name in self.chains:
            return False
        self.chains[name] = _FakeChain(name, domain_type)
        return True


@pytest.fixture
def fake_hierarchy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> list[_FakeHierarchyManager]:
    monkeypatch.chdir(tmp_path)
    _FakeHierarchyManager.chains = {}
    _FakeHierarchyManager.fail_create = False
    managers: list[_FakeHierarchyManager] = []

    def create_manager() -> _FakeHierarchyManager:
        manager = _FakeHierarchyManager()
        managers.append(manager)
        return manager

    monkeypatch.setattr(cli_store, "_new_hierarchy_manager", create_manager)
    return managers


def test_chain_create_uses_main_parent_and_manager_domain_type(
    fake_hierarchy: list[_FakeHierarchyManager],
) -> None:
    result = CliRunner().invoke(
        hrc, ["chain", "create", "supply_chain", "--name", "orders", "--parent", "main"]
    )

    assert result.exit_code == 0, result.output
    assert fake_hierarchy[0].create_calls == [("orders", "supply_chain")]
    assert _FakeHierarchyManager.chains["orders"].domain_type == "supply_chain"


def test_chain_create_rejects_unsupported_nested_parent(
    fake_hierarchy: list[_FakeHierarchyManager],
) -> None:
    result = CliRunner().invoke(
        hrc,
        ["chain", "create", "supply_chain", "--name", "child", "--parent", "orders"],
    )

    assert result.exit_code != 0
    assert "Nested parent chains are unsupported" in result.output
    assert fake_hierarchy == []


def test_chain_and_event_commands_reopen_manager_for_followup_invocations(
    fake_hierarchy: list[_FakeHierarchyManager],
) -> None:
    runner = CliRunner()
    created = runner.invoke(
        hrc, ["chain", "create", "supply_chain", "--name", "orders"]
    )
    added = runner.invoke(
        hrc,
        [
            "event",
            "add",
            "orders",
            "start_operation",
            "--entity-id",
            "ITEM-1",
            "--details",
            '{"line":"A1"}',
        ],
    )
    shown = runner.invoke(hrc, ["event", "show", "orders", "--entity-id", "ITEM-1"])

    assert created.exit_code == 0, created.output
    assert added.exit_code == 0, added.output
    assert shown.exit_code == 0, shown.output
    assert "ITEM-1" in shown.output
    assert len(fake_hierarchy) == 3


def test_cli_restores_chain_from_sqlite_between_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HRC_DATABASE_URL", raising=False)
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'hierarchy.db'}")

    runner = CliRunner()
    created = runner.invoke(
        hrc, ["chain", "create", "supply_chain", "--name", "cli_orders"]
    )
    restored_listing = runner.invoke(hrc, ["chain", "list"])

    assert created.exit_code == 0, created.output
    assert restored_listing.exit_code == 0, restored_listing.output
    assert "cli_orders (supply_chain)" in restored_listing.output


def test_chain_creation_failure_returns_nonzero_without_success_message(
    fake_hierarchy: list[_FakeHierarchyManager],
) -> None:
    _FakeHierarchyManager.fail_create = True

    result = CliRunner().invoke(
        hrc, ["chain", "create", "supply_chain", "--name", "orders"]
    )

    assert result.exit_code != 0
    assert "Successfully created" not in result.output
    assert "synthetic storage failure" in result.output


@pytest.mark.parametrize(
    "arguments, expected_message",
    [
        (["event", "add", "missing", "quality_check", "--entity-id", "ITEM-1"], "not found"),
        (
            [
                "event",
                "add",
                "orders",
                "quality_check",
                "--entity-id",
                "ITEM-1",
                "--details",
                "not-json",
            ],
            "Invalid JSON",
        ),
        (
            [
                "event",
                "add",
                "orders",
                "quality_check",
                "--entity-id",
                "ITEM-1",
                "--details",
                "[]",
            ],
            "JSON object",
        ),
    ],
)
def test_event_failures_return_nonzero(
    fake_hierarchy: list[_FakeHierarchyManager],
    arguments: list[str],
    expected_message: str,
) -> None:
    _FakeHierarchyManager.chains["orders"] = _FakeChain("orders", "supply_chain")

    result = CliRunner().invoke(hrc, arguments)

    assert result.exit_code != 0
    assert expected_message in result.output
    assert "Added '" not in result.output


def test_node_init_rejects_data_path_that_is_a_file(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("occupied", encoding="utf-8")

    result = CliRunner().invoke(hrc, ["node", "init", "--data-dir", str(blocker)])

    assert result.exit_code != 0
    assert "Could not create data directory" in result.output


def test_node_init_configuration_is_loaded_by_node_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in (
        "DATABASE_URL",
        "HRC_DATABASE_URL",
        "HRC_STORAGE_BACKEND",
        "HRC_NODE_ID",
        "NODE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://before/start")
    monkeypatch.setattr(settings, "NODE_ID", "before-start")
    captured: list[tuple[str, str, str, str, bool, str | None]] = []

    def capture_start(*_args: object, **kwargs: object) -> None:
        runtime_settings = get_settings()
        captured.append(
            (
                settings.DATABASE_URL,
                settings.NODE_ID,
                settings.STORAGE_BACKEND,
                runtime_settings.STORAGE_BACKEND,
                bool(kwargs["reload"]),
                os.environ.get("HRC_DATABASE_URL"),
            )
        )

    monkeypatch.setattr(node_cli.uvicorn, "run", capture_start)
    runner = CliRunner()
    initialized = runner.invoke(hrc, ["node", "init", "--data-dir", "./my_data"])
    config_path = tmp_path / "my_data" / "config.yaml"
    started = runner.invoke(
        hrc,
        [
            "--config",
            str(config_path),
            "node",
            "start",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
            "--reload",
        ],
    )

    assert initialized.exit_code == 0, initialized.output
    assert started.exit_code == 0, started.output
    configured_url = f"sqlite:///{tmp_path / 'my_data' / 'hierachain.db'}"
    assert captured == [(configured_url, "node_1", "sqlite", "sqlite", True, configured_url)]
    assert settings.DATABASE_URL == "postgresql://before/start"
    assert settings.NODE_ID == "before-start"
    assert not any(
        name in os.environ
        for name in ("HRC_DATABASE_URL", "HRC_STORAGE_BACKEND", "HRC_NODE_ID")
    )


def test_node_start_accepts_legacy_generated_yaml_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for name in (
        "DATABASE_URL",
        "HRC_DATABASE_URL",
        "HRC_STORAGE_BACKEND",
        "HRC_NODE_ID",
        "NODE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    config_path = tmp_path / "my_data" / "config.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        '# HieraChain Configuration\n'
        'database_url: "sqlite:///./my_data/hierachain.db"\n'
        'node_id: "node_1"\n',
        encoding="utf-8",
    )
    captured: list[tuple[str, str]] = []

    def capture_start(*_args: object, **_kwargs: object) -> None:
        captured.append((settings.DATABASE_URL, settings.NODE_ID))

    monkeypatch.setattr(node_cli.uvicorn, "run", capture_start)

    result = CliRunner().invoke(hrc, ["--config", str(config_path), "node", "start"])

    assert result.exit_code == 0, result.output
    assert captured == [("sqlite:///./my_data/hierachain.db", "node_1")]


@pytest.mark.parametrize(
    ("database_url", "expected_backend"),
    [
        ("sqlite:///./node.db", "sqlite"),
        ("postgresql://db.example.invalid:5432/node", "postgres"),
    ],
)
def test_node_config_infers_backend_for_fresh_runtime_settings_and_restores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    expected_backend: str,
) -> None:
    for name in ("DATABASE_URL", "HRC_DATABASE_URL", "HRC_STORAGE_BACKEND"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HRC_ENV", "development")
    prior_settings = get_settings()
    prior_database_url = prior_settings.DATABASE_URL
    prior_fresh_backend = prior_settings.STORAGE_BACKEND
    prior_singleton_backend = settings.STORAGE_BACKEND
    config_path = tmp_path / "config.yaml"
    config_path.write_text(json.dumps({"database_url": database_url}), encoding="utf-8")
    context = click.Context(hrc, info_name="hrc")

    try:
        cli_store.load_node_config(context, str(config_path))

        runtime_settings = get_settings()
        assert os.environ["HRC_STORAGE_BACKEND"] == expected_backend
        assert settings.STORAGE_BACKEND == expected_backend
        assert runtime_settings.STORAGE_BACKEND == expected_backend
        assert runtime_settings.DATABASE_URL == database_url
    finally:
        context.close()

    assert "HRC_STORAGE_BACKEND" not in os.environ
    assert "HRC_DATABASE_URL" not in os.environ
    assert settings.STORAGE_BACKEND == prior_singleton_backend
    assert get_settings().STORAGE_BACKEND == prior_fresh_backend
    assert get_settings().DATABASE_URL == prior_database_url


def test_node_config_preserves_explicit_storage_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HRC_DATABASE_URL", raising=False)
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("HRC_ENV", "development")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        json.dumps({"database_url": "postgresql://db.example.invalid:5432/node"}),
        encoding="utf-8",
    )
    context = click.Context(hrc, info_name="hrc")
    prior_database_url = get_settings().DATABASE_URL

    try:
        cli_store.load_node_config(context, str(config_path))

        assert os.environ["HRC_STORAGE_BACKEND"] == "sqlite"
        assert get_settings().STORAGE_BACKEND == "sqlite"
    finally:
        context.close()

    assert os.environ["HRC_STORAGE_BACKEND"] == "sqlite"
    assert get_settings().DATABASE_URL == prior_database_url
