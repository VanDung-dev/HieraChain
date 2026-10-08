"""CLI configuration and durable hierarchy access."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import click
from click.core import ParameterSource

from hierachain.config.settings import get_settings, settings
from hierachain.serialization import loads_json

logger = logging.getLogger(__name__)


def _parse_node_yaml(text: str) -> dict[str, Any]:
    """Parse the flat scalar YAML fields supported by the CLI config."""
    values: dict[str, Any] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        content = line.strip()
        if not content or content.startswith("#"):
            continue
        if content in {"---", "..."}:
            continue
        key, separator, raw_value = content.partition(":")
        if not separator or not key.strip():
            raise ValueError(f"Invalid configuration entry on line {line_number}")
        key = key.strip()
        if key in values:
            raise ValueError(f"Duplicate configuration field {key!r}")
        raw_value = raw_value.strip()
        if raw_value.startswith('"'):
            value = loads_json(raw_value)
        elif raw_value.startswith("'"):
            if len(raw_value) < 2 or not raw_value.endswith("'"):
                raise ValueError(f"Invalid quoted value on line {line_number}")
            value = raw_value[1:-1].replace("''", "'")
        else:
            value = raw_value.split(" #", maxsplit=1)[0].strip()
        values[key] = value
    return values


def _storage_backend_for_database_url(database_url: str) -> str | None:
    """Infer supported SQL backends from a configured database URL."""
    scheme = database_url.partition(":")[0].lower()
    if scheme in {"sqlite", "sqlite3"}:
        return "sqlite"
    if scheme in {"postgres", "postgresql", "postgresql+psycopg"}:
        return "postgres"
    return None


def load_node_config(ctx: click.Context, filepath: str) -> None:
    """Apply the supported YAML node settings, accepting JSON-compatible YAML too."""
    if not os.path.isfile(filepath):
        if ctx.get_parameter_source("config") != ParameterSource.DEFAULT:
            raise click.ClickException(f"Configuration file not found: {filepath}")
        return

    try:
        with open(filepath, encoding="utf-8") as config_file:
            text = config_file.read()
        try:
            values = loads_json(text)
        except json.JSONDecodeError:
            values = _parse_node_yaml(text)
    except (OSError, UnicodeError, ValueError) as exc:
        raise click.ClickException(f"Could not read node configuration {filepath}: {exc}") from exc

    if not isinstance(values, dict):
        raise click.ClickException("Node configuration must be an object")
    unsupported = set(values) - {"database_url", "node_id"}
    if unsupported:
        names = ", ".join(sorted(str(name) for name in unsupported))
        raise click.ClickException(f"Unsupported node configuration field(s): {names}")
    if not values:
        raise click.ClickException("Node configuration must set database_url or node_id")

    database_url = values.get("database_url")
    node_id = values.get("node_id")
    if database_url is not None and (not isinstance(database_url, str) or not database_url.strip()):
        raise click.ClickException("database_url must be a non-empty string")
    if node_id is not None and (not isinstance(node_id, str) or not node_id.strip()):
        raise click.ClickException("node_id must be a non-empty string")

    previous_database_url = settings.DATABASE_URL
    previous_node_id = settings.NODE_ID
    changed_environment: dict[str, str | None] = {}
    settings_class = type(get_settings())
    had_class_database_url = "DATABASE_URL" in settings_class.__dict__
    previous_class_database_url = getattr(settings_class, "DATABASE_URL", None)
    applied_config_database_url = False

    if database_url and not any(
        os.getenv(name, "").strip() for name in ("DATABASE_URL", "HRC_DATABASE_URL")
    ):
        applied_config_database_url = True
        changed_environment["HRC_DATABASE_URL"] = os.environ.get("HRC_DATABASE_URL")
        os.environ["HRC_DATABASE_URL"] = database_url
        settings.DATABASE_URL = database_url
        # The API lifespan obtains a fresh Settings object. Its class attribute was
        # captured when this module was imported, so update this environment's
        # settings class for the duration of this CLI invocation as well.
        setattr(settings_class, "DATABASE_URL", database_url)

        inferred_backend = _storage_backend_for_database_url(database_url)
        if inferred_backend and not os.getenv("HRC_STORAGE_BACKEND", "").strip():
            changed_environment["HRC_STORAGE_BACKEND"] = os.environ.get("HRC_STORAGE_BACKEND")
            os.environ["HRC_STORAGE_BACKEND"] = inferred_backend

    if node_id and not any(
        os.getenv(name, "").strip() for name in ("HRC_NODE_ID", "NODE_ID")
    ):
        changed_environment["HRC_NODE_ID"] = os.environ.get("HRC_NODE_ID")
        os.environ["HRC_NODE_ID"] = node_id
        settings.NODE_ID = node_id

    def restore_settings() -> None:
        settings.DATABASE_URL = previous_database_url
        settings.NODE_ID = previous_node_id
        if applied_config_database_url:
            if had_class_database_url:
                setattr(settings_class, "DATABASE_URL", previous_class_database_url)
            else:
                delattr(settings_class, "DATABASE_URL")
        for name, previous_value in changed_environment.items():
            if previous_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous_value

    ctx.call_on_close(restore_settings)


def _new_hierarchy_manager() -> Any:
    """Create a manager using the configured durable SQL backend."""
    from hierachain.hierarchical.hierarchy_manager import HierarchyManager

    return HierarchyManager()


def _close_hierarchy_manager(manager: Any) -> None:
    """Release command-scoped chain, journal, and storage resources."""
    close = getattr(manager, "close", None)
    if callable(close):
        close()
        return
    for chain in manager.get_all_sub_chains().values():
        try:
            chain.shutdown()
        except Exception:
            logger.exception("Could not shut down CLI sub-chain %s", getattr(chain, "name", "unknown"))

    try:
        manager.transaction_manager.journal.close()
    except Exception:
        logger.exception("Could not close CLI hierarchy transaction journal")

    storage = getattr(manager, "storage", None)
    if storage is not None:
        try:
            storage.close()
        except Exception:
            logger.exception("Could not close CLI hierarchy storage")


def get_hierarchy_manager(ctx: click.Context) -> Any:
    """Return the durable manager shared by commands in this invocation."""
    root = ctx.find_root()
    state = root.ensure_object(dict)
    manager = state.get("hierarchy_manager")
    if manager is not None:
        return manager

    try:
        manager = _new_hierarchy_manager()
    except Exception as exc:
        raise click.ClickException(f"Could not restore durable hierarchy: {exc}") from exc

    if getattr(manager, "storage", None) is None:
        _close_hierarchy_manager(manager)
        raise click.ClickException(
            "CLI chain and event commands require durable SQLite or PostgreSQL storage"
        )

    state["hierarchy_manager"] = manager
    root.call_on_close(lambda: _close_hierarchy_manager(manager))
    return manager


def get_sub_chain(ctx: click.Context, name: str) -> Any | None:
    """Return a registered sub-chain restored by the durable manager."""
    return get_hierarchy_manager(ctx).get_sub_chain(name)


def get_all_chains(ctx: click.Context) -> dict[str, Any]:
    """Return all registered sub-chains restored by the durable manager."""
    return get_hierarchy_manager(ctx).get_all_sub_chains()
