"""
Pytest configuration for HieraChain project.

Ensures project root is on sys.path so test imports like `import api`, `import core`,
`import hierarchical` resolve correctly during test collection.
"""

import json
import os

os.environ.setdefault("HRC_ENV", "test")
# prevent product .env from enabling auth/strict CORS in tests when .env is product
if os.getenv("HRC_ENV", "").lower() in ("test", "testing"):
    os.environ.setdefault("HRC_AUTH_ENABLED", "false")
import shutil
import sys
import time
from pathlib import Path

import pytest

from hierachain.config.settings import settings
from hierachain.security.security_utils import KeyPair

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
