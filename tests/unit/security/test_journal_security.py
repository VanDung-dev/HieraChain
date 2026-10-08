"""
Test suite for the TransactionJournal class.
"""

import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hierachain.config.settings import settings
from hierachain.error_mitigation import TransactionJournal
from hierachain.hierarchical import SubChain


def test_journal_rejects_unsupported_locking_before_creating_files(monkeypatch, tmp_path: Path) -> None:
    from hierachain.error_mitigation import journal as journal_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(journal_module, "fcntl", None)
    with pytest.raises(RuntimeError, match="requires POSIX"):
        TransactionJournal(storage_dir="journal")
    assert not (tmp_path / "data").exists()


def test_writer_lease_is_distinct_from_an_active_lock_extension(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    journal = TransactionJournal(storage_dir="journal", active_log_name="events.lock")
    try:
        assert journal.log_event({"entity_id": "E", "event": "accepted", "timestamp": 1.0})
        monkeypatch.setattr(journal, "_should_rotate", lambda: True)
        journal._rotate_if_needed()
        with pytest.raises(RuntimeError, match="owning writer"):
            TransactionJournal(storage_dir="journal", active_log_name="events.lock")
        assert [row["event"] for row in journal.replay()] == ["accepted"]
    finally:
        journal.close()


def test_journal_writer_lease_blocks_other_process_and_releases_on_close(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    journal = TransactionJournal(storage_dir="journal", active_log_name="events.arrow")
    repository = Path(__file__).resolve().parents[3]
    script = f"""
import sys
sys.path.insert(0, {str(repository)!r})
from hierachain.error_mitigation.journal import TransactionJournal
try:
    journal = TransactionJournal(storage_dir='journal', active_log_name='events.arrow')
except RuntimeError:
    sys.exit(17)
try:
    assert journal.log_event({{'entity_id': 'E', 'event': 'other-process', 'timestamp': 1.0}})
finally:
    journal.close()
"""
    try:
        blocked = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10)
        assert blocked.returncode == 17, blocked.stderr
        assert list(journal.replay()) == []
    finally:
        journal.close()
    allowed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10)
    assert allowed.returncode == 0, allowed.stderr
    reopened = TransactionJournal(storage_dir="journal", active_log_name="events.arrow")
    try:
        assert [row["event"] for row in reopened.replay()] == ["other-process"]
    finally:
        reopened.close()


@pytest.mark.parametrize("read_method", ["replay", "read_since"])
def test_legacy_parquet_archive_symlink_is_rejected(monkeypatch, tmp_path, read_method: str) -> None:
    monkeypatch.chdir(tmp_path)
    journal = TransactionJournal(storage_dir="journal", active_log_name="events.arrow")
    outside = tmp_path / "outside.parquet"
    outside.write_bytes(b"untrusted archive")
    (journal.storage_path / "events_legacy.parquet").symlink_to(outside)
    try:
        with pytest.raises(ValueError, match="Could not replay legacy Parquet"):
            if read_method == "replay":
                list(journal.replay())
            else:
                journal.read_since()
    finally:
        journal.close()


def test_directory_entries_are_fsynced_on_creation_and_rotation(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    fsynced = []
    real_fsync = os.fsync

    def record_fsync(descriptor: int) -> None:
        fsynced.append(stat.S_ISDIR(os.fstat(descriptor).st_mode))
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", record_fsync)
    journal = TransactionJournal(storage_dir="journal", active_log_name="events.arrow")
    try:
        assert any(fsynced)
        assert journal.log_event({"entity_id": "E", "event": "accepted", "timestamp": 1.0})
        fsynced.clear()
        monkeypatch.setattr(journal, "_should_rotate", lambda: True)
        journal._rotate_if_needed()
        assert fsynced.count(True) >= 2
        assert [row["event"] for row in journal.replay()] == ["accepted"]
    finally:
        journal.close()


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


def test_append_only_journal_round_trip(monkeypatch, tmp_path):
    """Events survive append-only writes and replay in insertion order."""
    monkeypatch.chdir(tmp_path)
    journal = TransactionJournal(storage_dir="journal", active_log_name="events.arrow")

    try:
        events = [
            {
                "event_id": "evt-1",
                "entity_id": "entity-1",
                "event": "created",
                "timestamp": time.time(),
                "details": {"initial_data": {"asset_type": "equipment"}, "count": 1, "flag": True},
            },
            {
                "event_id": "evt-2",
                "entity_id": "entity-2",
                "event": "updated",
                "timestamp": time.time(),
            },
        ]
        for event in events:
            assert journal.log_event(event)

        replayed = list(journal.replay())
        assert [event["event_id"] for event in replayed] == ["evt-1", "evt-2"]
        assert replayed[0]["details"] == events[0]["details"]
        assert set(replayed[0]) == set(events[0])
    finally:
        journal.close()


def test_sub_chain_init_validation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify SubChain constructor validation"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///test.db")

    # Valid
    chain = SubChain("valid_name")
    chain.shutdown()

    # Invalid
    with pytest.raises(ValueError, match="Invalid SubChain name"):
        SubChain("invalid/name")

    with pytest.raises(ValueError, match="Invalid SubChain name"):
        SubChain("../traversal")
