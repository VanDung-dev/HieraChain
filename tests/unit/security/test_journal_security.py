"""
Test suite for the TransactionJournal class.
"""

import os
import tempfile
from pathlib import Path
from hierachain.error_mitigation.journal import TransactionJournal

def test_path_traversal_prevention():
    """
    Verify that providing directory traversal characters in active_log_name
    does not result in file creation outside the storage directory.
    CWE-22 Mitigation Test.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir) / "journal"
        
        # Attack payload: Attempt to traverse out of "journal"
        evil_log_name = "../evil.log"
        
        # Initialize journal
        journal = TransactionJournal(storage_dir=str(storage_dir), active_log_name=evil_log_name)
        
        try:
            # Check logical path resolution
            expected_file = storage_dir.resolve() / "evil.log"
            
            assert journal.active_log_file == expected_file, \
                f"Journal file path {journal.active_log_file} does not match expected secure path {expected_file}"
            
            assert journal.active_log_file.parent == storage_dir.resolve(), \
                "Journal file created outside of storage directory!"
                
            assert journal.active_log_file.name == "evil.log", \
                "Filename should remain 'evil.log' after sanitization"
                
        finally:
            journal.close()

def test_storage_dir_absolute_resolution():
    """
    Verify that relative storage directories are resolved to absolute paths.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        relative_path = "relative_journal"
        
        # Change cwd to tmp_dir momentarily to test relative resolution
        original_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            journal = TransactionJournal(storage_dir=relative_path, active_log_name="test.log")
            try:
                assert journal.storage_path.is_absolute(), "Storage path must be absolute"
                # Resolve both to ensure handle 8.3 short paths on Windows
                assert journal.storage_path.resolve() == (Path(tmp_dir) / relative_path).resolve()
            finally:
                journal.close()
        finally:
            os.chdir(original_cwd)
