"""
Unit tests for MasterKeyProvider module.

Tests cover key loading from environment variables, files,
auto-generation, security checks, and error handling.
"""

import os
import base64
import secrets
import pytest

from hierachain.security.master_key_provider import (
    MasterKeyProvider,
    MasterKeyError,
)


# --- Fixtures ---

@pytest.fixture
def temp_key_dir(tmp_path):
    """Create a temporary directory for key files."""
    key_dir = tmp_path / "config"
    key_dir.mkdir()
    return key_dir


@pytest.fixture
def valid_key():
    """Generate a valid 32-byte master key."""
    return secrets.token_bytes(32)


@pytest.fixture
def valid_key_b64(valid_key):
    """Base64-encoded valid key for env var usage."""
    return base64.b64encode(valid_key).decode()


@pytest.fixture
def key_file(temp_key_dir, valid_key):
    """Create a key file with a valid key."""
    path = temp_key_dir / "master_backup_key.key"
    path.write_bytes(valid_key)
    return str(path)


# --- Test: Load from Environment Variable ---

def test_load_from_env_var(valid_key, valid_key_b64, monkeypatch):
    """Test loading master key from environment variable."""
    monkeypatch.setenv("HRC_MASTER_BACKUP_KEY", valid_key_b64)

    provider = MasterKeyProvider({"source": "env"})
    result = provider.get_master_key()

    assert result == valid_key
    assert len(result) == 32


def test_load_from_env_var_auto_mode(valid_key, valid_key_b64, monkeypatch):
    """Test auto mode prefers env var over file."""
    monkeypatch.setenv("HRC_MASTER_BACKUP_KEY", valid_key_b64)

    provider = MasterKeyProvider({"source": "auto"})
    result = provider.get_master_key()

    assert result == valid_key


def test_env_var_invalid_base64(monkeypatch):
    """Test handling of invalid base64 in env var."""
    monkeypatch.setenv("HRC_MASTER_BACKUP_KEY", "not-valid-base64!!!")

    provider = MasterKeyProvider({"source": "env"})
    with pytest.raises(MasterKeyError):
        provider.get_master_key()


def test_env_var_wrong_length(monkeypatch):
    """Test rejection of key with wrong length from env var."""
    short_key = base64.b64encode(b"short").decode()
    monkeypatch.setenv("HRC_MASTER_BACKUP_KEY", short_key)

    provider = MasterKeyProvider({"source": "env"})
    with pytest.raises(MasterKeyError):
        provider.get_master_key()


def test_env_var_not_set():
    """Test error when env var is required but not set."""
    # Ensure env var is not set
    os.environ.pop("HRC_MASTER_BACKUP_KEY", None)

    provider = MasterKeyProvider({"source": "env"})
    with pytest.raises(MasterKeyError):
        provider.get_master_key()


# --- Test: Load from File ---

def test_load_from_file(key_file, valid_key):
    """Test loading master key from file."""
    provider = MasterKeyProvider({"source": "file", "key_file": key_file})
    result = provider.get_master_key()
    assert result == valid_key


def test_load_from_file_legacy_fernet(temp_key_dir):
    """Test loading legacy Fernet key (base64 encoded, 44 bytes)."""
    raw_key = secrets.token_bytes(32)
    fernet_key = base64.urlsafe_b64encode(raw_key)
    assert len(fernet_key) == 44

    path = temp_key_dir / "legacy.key"
    path.write_bytes(fernet_key)

    provider = MasterKeyProvider({"source": "file", "key_file": str(path)})
    result = provider.get_master_key()
    assert result == raw_key


def test_file_not_found():
    """Test error when key file does not exist."""
    provider = MasterKeyProvider({"source": "file", "key_file": "/nonexistent/path/key.key"})
    with pytest.raises(MasterKeyError):
        provider.get_master_key()


def test_file_wrong_key_length(temp_key_dir):
    """Test rejection of file with wrong key length."""
    path = temp_key_dir / "bad.key"
    path.write_bytes(b"too_short")

    provider = MasterKeyProvider({"source": "file", "key_file": str(path)})
    with pytest.raises(MasterKeyError):
        provider.get_master_key()


# --- Test: Auto-Generate ---

def test_auto_generate_when_no_source(tmp_path, monkeypatch):
    """Test auto-generation when no env var or file exists."""
    os.environ.pop("HRC_MASTER_BACKUP_KEY", None)
    key_file = str(tmp_path / "config" / "new_key.key")

    provider = MasterKeyProvider({"source": "auto", "key_file": key_file})
    result = provider.get_master_key()

    assert len(result) == 32
    assert os.path.exists(key_file)

    # Verify persisted key matches
    with open(key_file, "rb") as f:
        assert f.read() == result


def test_auto_fallback_invalid_env_to_file(key_file, valid_key, monkeypatch):
    """Test auto mode falls back to file when env var is invalid."""
    monkeypatch.setenv("HRC_MASTER_BACKUP_KEY", "invalid!!!")

    provider = MasterKeyProvider({"source": "auto", "key_file": key_file})
    result = provider.get_master_key()
    assert result == valid_key


# --- Test: Caching ---

def test_key_is_cached(key_file, valid_key):
    """Test that key is cached after first load."""
    provider = MasterKeyProvider({"source": "file", "key_file": key_file})

    result1 = provider.get_master_key()
    result2 = provider.get_master_key()

    assert result1 == result2
    assert result1 is result2  # Same object reference (cached)


# --- Test: Security Checks ---

def test_check_key_file_security_public_dir(tmp_path):
    """Test warning for key file in a public directory."""
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    key_file = public_dir / "master.key"
    key_file.write_bytes(secrets.token_bytes(32))

    warnings = MasterKeyProvider.check_key_file_security(str(key_file))
    assert any("public" in w.lower() for w in warnings)


def test_check_key_file_security_nonexistent():
    """Test no warnings for nonexistent file."""
    warnings = MasterKeyProvider.check_key_file_security("/does/not/exist.key")
    assert warnings == []


def test_check_key_file_security_production_warning(key_file, monkeypatch):
    """Test production warning for file-based key."""
    monkeypatch.setenv("HRC_ENV", "product")
    warnings = MasterKeyProvider.check_key_file_security(key_file)
    assert any("production" in w.lower() for w in warnings)


# --- Test: Custom Configuration ---

def test_custom_env_var_name(valid_key, monkeypatch):
    """Test using a custom environment variable name."""
    custom_b64 = base64.b64encode(valid_key).decode()
    monkeypatch.setenv("MY_CUSTOM_KEY", custom_b64)

    provider = MasterKeyProvider({
        "source": "env",
        "env_var": "MY_CUSTOM_KEY",
    })
    result = provider.get_master_key()
    assert result == valid_key


def test_default_config():
    """Test MasterKeyProvider with default (None) config."""
    os.environ.pop("HRC_MASTER_BACKUP_KEY", None)
    provider = MasterKeyProvider()
    # Should not raise during init
    assert provider.source == "auto"
    assert provider.env_var == "HRC_MASTER_BACKUP_KEY"
