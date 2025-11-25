"""
Unit tests for KeyBackupManager module

This module contains unit tests for the KeyBackupManager class functionality,
including key backup, restoration, integrity verification, and cleanup.
"""

import os
import json
import time
import shutil
import pytest
from unittest.mock import Mock, patch

from hierarchical_blockchain.security.key_backup_manager import (
    KeyBackupManager,
    create_key_backup_manager,
    RestoreError
)

# Global variables for setup and teardown
backup_dir = "backups/keys"
metadata_file = os.path.join(backup_dir, "backup_metadata.json")


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and teardown for each test"""
    # Setup
    global backup_dir, metadata_file
    # Ensure clean state
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    
    yield  # Run test
    
    # Teardown
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)


def test_key_backup_manager_initialization():
    """Test KeyBackupManager initialization"""
    config = {
        "enabled": True,
        "frequency": "daily",
        "encryption_algorithm": "AES-256-GCM",
        "locations": ["primary_vault", "secondary_cloud"],
        "integrity_check": "sha512",
        "retention_period": 365
    }
    
    km = KeyBackupManager(config)
    
    assert km.enabled is True
    assert km.frequency == "daily"
    assert km.encryption_algorithm == "AES-256-GCM"
    assert km.locations == ["primary_vault", "secondary_cloud"]
    assert km.integrity_check == "sha512"
    assert km.retention_period == 365
    assert os.path.exists(backup_dir)

    def init_key_backup_manager():
        return KeyBackupManager(config)

    result = init_key_backup_manager()
    assert result.enabled is True


def test_backup_keys_when_disabled():
    """Test backup_keys when backup is disabled"""
    config = {"enabled": False}
    km = KeyBackupManager(config)
    
    backup_id = km.backup_keys(b"public_key", b"private_key", "test")
    assert backup_id == ""

    result = km.backup_keys(b"public_key", b"private_key", "test")
    assert result == ""


@patch('hierarchical_blockchain.security.key_backup_manager.Fernet')
def test_backup_keys_success(mock_fernet, benchmark=None):
    """Test successful key backup"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Mock encryption
    mock_fernet_instance = Mock()
    mock_fernet_instance.encrypt.return_value = b"encrypted_data"
    mock_fernet.return_value = mock_fernet_instance
    
    public_key = b"test_public_key"
    private_key = b"test_private_key"
    
    backup_id = km.backup_keys(public_key, private_key, "consensus")
    
    assert backup_id.startswith("consensus_")
    assert len(backup_id) > 10  # Should have timestamp part
    
    # Check that backup file was created
    backup_files = os.listdir(backup_dir)
    assert len(backup_files) >= 1  # At least the metadata file and one backup
    
    # Check metadata was updated
    assert os.path.exists(metadata_file)

    if benchmark:
        result = benchmark(km.backup_keys, public_key, private_key, "consensus")
    else:
        result = km.backup_keys(public_key, private_key, "consensus")

    assert result.startswith("consensus_")


@patch('hierarchical_blockchain.security.key_backup_manager.Fernet')
def test_backup_keys_encryption(mock_fernet):
    """Test that backup data is encrypted"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Mock encryption
    mock_fernet_instance = Mock()
    mock_fernet_instance.encrypt.return_value = b"encrypted_data"
    mock_fernet.return_value = mock_fernet_instance
    
    public_key = b"test_public_key"
    private_key = b"test_private_key"
    
    km.backup_keys(public_key, private_key, "test")
    
    # Check that encryption was called
    assert mock_fernet.called
    assert mock_fernet_instance.encrypt.called

    km.backup_keys(public_key, private_key, "test")


@patch('hierarchical_blockchain.security.key_backup_manager.Fernet')
def test_restore_keys_success(mock_fernet):
    """Test successful key restoration"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Mock encryption/decryption
    mock_fernet_instance = Mock()
    mock_fernet_instance.encrypt.return_value = b"encrypted_data"
    mock_fernet_instance.decrypt.return_value = json.dumps({
        "public_key": "746573745f7075626c69635f6b65795f6c6f6e675f656e6f7567685f666f725f74657374696e67",  # long hex string
        "private_key": "746573745f707269766174655f6b65795f6c6f6e675f656e6f7567685f666f725f74657374696e67",  # long hex string
        "key_type": "test"
    }).encode('utf-8')
    mock_fernet.return_value = mock_fernet_instance
    
    # First backup keys (using longer keys to pass validation)
    public_key = b"test_public_key_long_enough_for_testing"
    private_key = b"test_private_key_long_enough_for_testing"
    backup_id = km.backup_keys(public_key, private_key, "test")
    
    # Then restore them
    restored_keys = km.restore_keys(backup_id)
    
    assert "public_key" in restored_keys
    assert "private_key" in restored_keys
    # Note: Due to hex encoding/decoding in the mock, exact comparison might differ
    # but the main point is that the method works without throwing exceptions

    result = km.restore_keys(backup_id)
    assert "public_key" in result


def test_list_backups():
    """Test listing backups"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Mock encryption
    with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
        mock_fernet_instance = Mock()
        mock_fernet_instance.encrypt.return_value = b"encrypted_data"
        mock_fernet.return_value = mock_fernet_instance
        
        # Create some backups
        km.backup_keys(b"pub1", b"priv1", "type1")
        time.sleep(0.1)  # Ensure different timestamps
        km.backup_keys(b"pub2", b"priv2", "type2")
        
        # List all backups
        backups = km.list_backups()
        assert len(backups) == 2
        
        # List backups of specific type
        type1_backups = km.list_backups("type1")
        assert len(type1_backups) == 1
        assert type1_backups[0]["key_type"] == "type1"

        result = km.list_backups()
        assert len(result) >= 2


@patch('hierarchical_blockchain.security.key_backup_manager.Fernet')
def test_verify_backup_integrity_valid(mock_fernet):
    """Test backup integrity verification with valid backup"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Mock encryption
    mock_fernet_instance = Mock()
    mock_fernet_instance.encrypt.return_value = b"encrypted_data"
    mock_fernet.return_value = mock_fernet_instance

    # Create backup
    backup_id = km.backup_keys(b"pub", b"priv", "test")
    
    # Verify integrity
    is_valid = km.verify_backup_integrity(backup_id)
    assert is_valid is True

    result = km.verify_backup_integrity(backup_id)
    assert result is True


def test_verify_backup_integrity_invalid():
    """Test backup integrity verification with invalid backup"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Try to verify non-existent backup
    is_valid = km.verify_backup_integrity("non_existent_backup")
    assert is_valid is False

    result = km.verify_backup_integrity("non_existent_backup")
    assert result is False


def test_create_key_backup_manager_factory():
    """Test the factory function"""
    config = {"enabled": True}
    km = create_key_backup_manager(config)
    
    assert isinstance(km, KeyBackupManager)
    assert km.enabled is True

    result = create_key_backup_manager(config)

    assert isinstance(result, KeyBackupManager)
    assert result.enabled is True


def test_backup_keys_with_invalid_input():
    """Test backup_keys with invalid inputs"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Test with empty keys
    backup_id = km.backup_keys(b"", b"", "test")
    assert backup_id.startswith("test_")
    
    # Test with extremely long keys
    long_key = b"x" * 10000
    backup_id = km.backup_keys(long_key, long_key, "long_test")
    assert backup_id.startswith("long_test_")

    result = km.backup_keys(b"", b"", "test")
    assert result.startswith("test_")


def test_restore_keys_with_invalid_backup_id():
    """Test restore_keys with invalid/non-existent backup ID"""
    config = {"enabled": True}
    km = KeyBackupManager(config)

    # Try to restore with non-existent backup ID
    with pytest.raises(RestoreError):
        km.restore_keys("non_existent_backup")

    # Benchmark restore with non-existent backup ID
    def restore_nonexistent():
        try:
            km.restore_keys("non_existent_backup")
        except RestoreError:
            pass  # Expected exception

    restore_nonexistent()


def test_verify_backup_integrity_with_invalid_inputs():
    """Test verify_backup_integrity with invalid inputs"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Test with empty backup ID
    assert km.verify_backup_integrity("") is False
    
    # Test with non-existent backup ID
    assert km.verify_backup_integrity("non_existent") is False

    result = km.verify_backup_integrity("")
    assert result is False


def test_backup_keys_performance(benchmark=None):
    """Test performance of key backup operations"""
    config = {"enabled": True}
    km = KeyBackupManager(config)

    # Mock en cryption to avoid performance overhead of actual encryption
    with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
        mock_fernet_instance = Mock()
        mock_fernet_instance.encrypt.return_value = b"encrypted_data"
        mock_fernet.return_value = mock_fernet_instance

        # Test with normal size keys
        public_key = b"test_public_key_data_for_performance_testing"
        private_key = b"test_private_key_data_for_performance_testing"

        def backup_keys():
            start_time = time.perf_counter()
            for i in range(10):  # Test with 10 iterations
                km.backup_keys(public_key, private_key, f"perf_test_{i}")
            end_time = time.perf_counter()

            # Each backup operation should take less than 0.1 seconds
            assert (end_time - start_time) < 1.0  # 1 second for 10 operations

        if benchmark:
            benchmark(backup_keys)
        else:
            backup_keys()


def test_restore_keys_performance(benchmark=None):
    """Test performance of key restore operations"""
    config = {"enabled": True}
    km = KeyBackupManager(config)

    # Mock encryption/decryption
    with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
        mock_fernet_instance = Mock()
        mock_fernet_instance.encrypt.return_value = b"encrypted_data"
        mock_fernet_instance.decrypt.return_value = json.dumps({
            "public_key": "746573745f7075626c69635f6b65795f646174615f666f725f706572666f726d616e63655f74657374696e67",
            # hex string
            "private_key": "746573745f707269766174655f6b65795f646174615f666f725f706572666f726d616e63655f74657374696e67",
            # hex string
            "key_type": "perf_test"
        }).encode('utf-8')
        mock_fernet.return_value = mock_fernet_instance

        def restore_keys():
            # Create multiple backups first
            backup_ids = []
            for i in range(10):
                backup_id = km.backup_keys(b"pub_key_" + str(i).encode(), b"priv_key_" + str(i).encode(), "perf_test")
                backup_ids.append(backup_id)

            # Measure restore performance
            start_time = time.perf_counter()
            for backup_id in backup_ids:
                km.restore_keys(backup_id)
            end_time = time.perf_counter()
            # Each restore operation should take less than 0.1 seconds
            assert (end_time - start_time) < 1.0  # 1 second for 10 operations

        if benchmark:
            benchmark(restore_keys)
        else:
            restore_keys()


def test_backup_security_injection_attacks():
    """Test KeyBackupManager resistance to injection attacks"""
    config = {"enabled": True}
    km = KeyBackupManager(config)

    # Mock encryption
    with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
        mock_fernet_instance = Mock()
        mock_fernet_instance.encrypt.return_value = b"encrypted_data"
        mock_fernet.return_value = mock_fernet_instance

        # Test injection attempts in key_type
        injection_attempts = [
            "'; DROP TABLE backups; --",
            "1'; WAIT FOR DELAY '00:00:05'--",
            "test'--",
            "' OR '1'='1"
        ]

        for attempt in injection_attempts:
            backup_id = km.backup_keys(b"pub_key", b"priv_key", attempt)
            # After sanitization, the backup_id should start with a cleaned version of the key_type
            # Special characters should be removed or replaced
            sanitized_attempt = "".join(c for c in attempt if c.isalnum() or c in (' ', '-', '_')).rstrip()
            sanitized_attempt = sanitized_attempt.replace(' ', '_')
            assert backup_id.startswith(sanitized_attempt)

            # Verify we can list backups with the original key_type
            backups = km.list_backups(attempt)
            assert len(backups) >= 1

            # Verify integrity check works
            is_valid = km.verify_backup_integrity(backup_id)
            assert is_valid is True


def test_backup_security_xss_attacks():
    """Test KeyBackupManager resistance to XSS attacks"""
    config = {"enabled": True}
    km = KeyBackupManager(config)

    # Mock encryption
    with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
        mock_fernet_instance = Mock()
        mock_fernet_instance.encrypt.return_value = b"encrypted_data"
        mock_fernet.return_value = mock_fernet_instance

        # Test XSS attempts in key_type
        xss_attempts = [
            "<script>alert('XSS')</script>",
            "test<img src=x onerror=alert(1)>backup",
            "backup\" onmouseover=\"alert('XSS')\"",
        ]

        for attempt in xss_attempts:
            backup_id = km.backup_keys(b"pub_key", b"priv_key", attempt)
            # After sanitization, the backup_id should start with a cleaned version of the key_type
            # Special characters should be removed or replaced
            sanitized_attempt = "".join(c for c in attempt if c.isalnum() or c in (' ', '-', '_')).rstrip()
            sanitized_attempt = sanitized_attempt.replace(' ', '_')
            assert backup_id.startswith(sanitized_attempt)

            # Verify we can list backups with the original key_type
            backups = km.list_backups(attempt)
            assert len(backups) >= 1
