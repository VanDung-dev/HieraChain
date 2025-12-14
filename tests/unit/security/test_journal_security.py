"""
Test suite for the TransactionJournal class.
"""

import pytest

from hierachain.error_mitigation.journal import TransactionJournal
from hierachain.hierarchical.sub_chain import SubChain


def test_filename_validation_strict():
    """
    Verify strict filename allowlist regex.
    Allowed: alphanumeric, underscore, hyphen, single dot extension.
    """
    # Valid names
    TransactionJournal._validate_filename("current.log")
    TransactionJournal._validate_filename("journal_2024-01.arrow")
    TransactionJournal._validate_filename("plainfile")

    # Invalid names
    invalid_cases = [
        "../evil.log",        # Traversal
        "folder/file.log",    # Directory separator
        "file!.log",          # Special char
        "log.tar.gz",         # Double extension (strict rule)
        ".hidden",            # Hidden file (starts with dot)
        " ",                  # Empty/space
    ]

    for name in invalid_cases:
        with pytest.raises(ValueError, match="Security: Invalid filename"):
            TransactionJournal._validate_filename(name)


def test_storage_dir_traversal_check():
    """
    Verify that storage_dir cannot contain '..' components.
    """
    with pytest.raises(ValueError, match="Path traversal sequence"):
        TransactionJournal(storage_dir="data/../etc", active_log_name="test.log")


def test_log_file_escape_prevention(monkeypatch, tmp_path):
    """
    Verify logic that ensures log file is inside storage path.
    """
    # Setup fake data root structure
    cwd_mock = tmp_path
    monkeypatch.chdir(cwd_mock)

    data_dir = cwd_mock / "data"
    data_dir.mkdir()

    storage_dir = data_dir / "journal"
    storage_dir.mkdir()

    # Should pass
    j1 = TransactionJournal(storage_dir=str(storage_dir), active_log_name="ok.log")
    j1.close() # Close to release file handle for Windows cleanup

    # Using absolute path outside of data should fail (if we could force it)
    # But the check `startswith` is robust.

    # Test that we can't initialize if storage_dir is outside data (even if valid path)
    outside_dir = cwd_mock / "outside"
    outside_dir.mkdir()
    with pytest.raises(ValueError, match="Security: Storage path"):
        TransactionJournal(storage_dir=str(outside_dir), active_log_name="ok.log")


def test_sub_chain_init_validation():
    """Verify SubChain constructor validation"""
    # Valid
    SubChain("valid_name")

    # Invalid
    with pytest.raises(ValueError, match="Invalid SubChain name"):
        SubChain("invalid/name")

    with pytest.raises(ValueError, match="Invalid SubChain name"):
        SubChain("../traversal")
