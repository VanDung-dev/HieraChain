"""
Pytest configuration for HieraChain project.

Ensures project root is on sys.path so test imports like `import api`, `import core`,
`import hierarchical` resolve correctly during test collection.
"""

import json
import os
from collections.abc import Iterator

os.environ.setdefault("HRC_ENV", "test")
if os.getenv("HRC_ENV", "").lower() in ("test", "testing"):
    os.environ.setdefault("HRC_AUTH_ENABLED", "false")
import atexit
import shutil
import sys
import time
import uuid
from pathlib import Path

import pytest

from hierachain.config.settings import settings
from hierachain.security.security_utils import KeyPair

_TESTS_DIR = os.path.dirname(__file__)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from test_infra import (  # noqa: E402
    cleanup_container,
    create_temp_postgres_db,
    drop_postgres_db,
    ensure_durable_redis,
    resolve_postgres_base_url,
)

_infra_state: dict[str, object] = {}


def _provision_test_infrastructure() -> None:
    if _infra_state.get("done"):
        return
    _infra_state["done"] = True

    pg_base = resolve_postgres_base_url()
    if pg_base:
        _infra_state["pg_base"] = pg_base
        os.environ.setdefault("HRC_P2_TEST_POSTGRES_URL", pg_base)

    if not os.getenv("HRC_P2_TEST_REDIS_URL") or not os.getenv("HRC_TEST_REDIS_PORT"):
        result = ensure_durable_redis("hrc-test-redis-shared")
        if result:
            url, port, name = result
            _infra_state["shared_redis"] = name
            os.environ.setdefault("HRC_P2_TEST_REDIS_URL", url)
            os.environ.setdefault("HRC_TEST_REDIS_PORT", str(port))

    if not os.getenv("HRC_REDIS_LEDGER_TEST_URL") or not os.getenv(
        "HRC_REDIS_LEDGER_TEST_CONTAINER"
    ):
        result = ensure_durable_redis(f"hrc-ledger-test-{uuid.uuid4().hex[:8]}")
        if result:
            url, port, name = result
            _infra_state["ledger_redis"] = name
            os.environ.setdefault("HRC_REDIS_LEDGER_TEST_URL", url)
            os.environ.setdefault("HRC_REDIS_LEDGER_TEST_CONTAINER", name)


def _cleanup_test_infrastructure() -> None:
    for key in ("shared_redis", "ledger_redis"):
        name = _infra_state.get(key)
        if isinstance(name, str):
            cleanup_container(name)
            _infra_state.pop(key, None)


_provision_test_infrastructure()
atexit.register(_cleanup_test_infrastructure)


def _needs_isolated_postgres_db(node: pytest.Item) -> bool:
    callspec = getattr(node, "callspec", None)
    if callspec and "postgres" in str(callspec.params):
        return True
    path = str(getattr(node, "fspath", ""))
    if "test_live_backends" in path:
        return False
    for marker in (
        "test_bulk_storage",
        "test_cli_postgres",
        "test_block_event_ownership",
        "test_registry_multiworker",
    ):
        if marker in path:
            return True
    return False


@pytest.fixture(autouse=True)
def _isolated_postgres_test_db(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    pg_base = _infra_state.get("pg_base")
    if not isinstance(pg_base, str) or not _needs_isolated_postgres_db(request.node):
        yield
        return
    try:
        db_url, db_name = create_temp_postgres_db(pg_base)
    except Exception:
        yield
        return
    monkeypatch.setenv("HRC_TEST_POSTGRES_URL", db_url)
    try:
        yield
    finally:
        drop_postgres_db(pg_base, db_name)

# Compute project root (parent of this tests directory)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Data directory containing journal files
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--fail-on-skip", action="store_true", help="Fail required backend jobs on skipped tests")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if session.config.getoption("--fail-on-skip"):
        reporter = session.config.pluginmanager.getplugin("terminalreporter")
        if reporter is not None and reporter.stats.get("skipped"):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture
def isolated_chain_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use per-case SQLite and journals for backend-independent chain tests."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HRC_STORAGE_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'main.db'}")


@pytest.fixture
def isolated_api_hierarchy(
    isolated_chain_storage: None, monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    from hierachain.api.ledger import depds

    monkeypatch.setattr(depds, "_hierarchy_manager", None)
    monkeypatch.setattr(depds, "_entity_tracer", None)
    monkeypatch.setattr(depds, "_hierarchy_retry_at", 0.0)
    try:
        yield
    finally:
        depds.close_hierarchy_manager()


def _remove_data_dir_with_retry(max_retries=3, delay=0.5):
    """Remove data directory with retry logic for Windows file locks."""
    if not os.path.exists(_DATA_DIR):
        return
    
    for attempt in range(max_retries):
        try:
            shutil.rmtree(_DATA_DIR)
            return
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(delay)
            # On last attempt, ignore the error (files will be cleaned next run)
        except OSError:
            # Ignore other errors during cleanup
            return


@pytest.fixture(autouse=True, scope="session")
def clean_journal_data():
    """Remove journal data at start/end of test session to prevent state pollution."""
    _remove_data_dir_with_retry()
    yield
    # Cleanup after all tests complete (best effort)
    _remove_data_dir_with_retry()


@pytest.fixture(autouse=True, scope="session")
def configured_block_identity(tmp_path_factory):
    """Give test chains a fixed signer and explicit public-key trust source."""
    keypair = KeyPair.generate()
    config_dir = tmp_path_factory.mktemp("block-identity")
    identity_file = config_dir / "identity.json"
    trust_file = config_dir / "trusted.json"
    identity_file.write_text(json.dumps({
        "node_id": "test-node",
        "msp_id": "Test-MSP",
        "signing_key": keypair.private_key,
        "signing_public_key": keypair.public_key,
        "transport_secret_key": "",
        "transport_public_key": "",
    }))
    identity_file.chmod(0o600)
    trust_file.write_text(json.dumps({"test-node": keypair.public_key}))
    previous_identity = settings.VALIDATOR_IDENTITY_PATH
    previous_trust = settings.BLOCK_TRUSTED_KEYS_FILE
    settings.VALIDATOR_IDENTITY_PATH = str(identity_file)
    settings.BLOCK_TRUSTED_KEYS_FILE = str(trust_file)
    yield
    settings.VALIDATOR_IDENTITY_PATH = previous_identity
    settings.BLOCK_TRUSTED_KEYS_FILE = previous_trust
