"""
Test coverage analysis for security modules.

This module contains tests specifically designed to increase code coverage
and test important conditional branches in the security modules.
"""

import json
import time
from unittest.mock import Mock, patch

from hierarchical_blockchain.security.key_manager import KeyManager
from hierarchical_blockchain.security.key_backup_manager import (
    KeyBackupManager,
    RestoreError,
    BackupError
)
from hierarchical_blockchain.security.msp import (
    HierarchicalMSP,
    CertificateAuthority,
    OrganizationPolicies
)


def test_key_manager_storage_backends():
    """Test KeyManager with different storage backends"""
    # Test with dict-based storage (default)
    km_dict = KeyManager()
    key1 = km_dict.create_key("user1", ["read"])
    assert km_dict.is_valid(key1) is True
    
    # Test with mock Redis-like storage
    mock_redis = Mock()
    mock_redis.get.return_value = None  # Key not found initially
    
    km_redis = KeyManager(storage_backend=mock_redis)
    key2 = km_redis.create_key("user2", ["write"])
    
    # Check that storage was called
    mock_redis.set.assert_called()
    assert "api_key:" in mock_redis.set.call_args[0][0]  # Check key prefix
    
    # Test retrieval
    key_data = json.dumps({
        'user_id': 'user2',
        'permissions': ['write'],
        'created_at': time.time()
    })
    mock_redis.get.return_value = key_data

    def validate_key():
        return km_redis.is_valid(key2)

    result = validate_key()
    assert result is True
    mock_redis.get.assert_called()


def test_key_manager_cache_mechanisms():
    """Test KeyManager caching mechanisms"""
    km = KeyManager()
    key = km.create_key("cache_test_user", ["read", "write"])
    
    # Initially not cached
    assert key not in km.key_cache
    
    # Cache the key
    km.cache_key(key, ttl=1)  # 1 second TTL
    
    # Now should be cached
    assert key in km.key_cache
    assert km.key_cache[key]['ttl'] == 1
    
    # Test cache expiration
    cached_at = km.key_cache[key]['cached_at']
    km.key_cache[key]['cached_at'] = cached_at - 2  # Make it 2 seconds old
    
    # Should not use expired cache
    def get_key_data():
        return km._get_key_data(key)

    result = get_key_data()
    assert result is not None


def test_key_backup_manager_configurations():
    """Test KeyBackupManager with different configurations"""
    # Test with minimal configuration
    minimal_config = {"enabled": True}
    km_min = KeyBackupManager(minimal_config)
    assert km_min.enabled is True
    assert km_min.frequency == "daily"  # Default
    
    # Test with full configuration
    full_config = {
        "enabled": False,
        "frequency": "hourly",
        "encryption_algorithm": "AES-128-GCM",
        "locations": ["local", "cloud", "remote"],
        "integrity_check": "sha256",
        "retention_period": 180
    }

    def create_backup_manager():
        return KeyBackupManager(full_config)

    km_full=create_backup_manager()

    assert km_full.enabled is False
    assert km_full.frequency == "hourly"
    assert km_full.encryption_algorithm == "AES-128-GCM"
    assert km_full.locations == ["local", "cloud", "remote"]
    assert km_full.integrity_check == "sha256"
    assert km_full.retention_period == 180


def test_key_backup_manager_edge_cases():
    """Test KeyBackupManager edge cases and error conditions"""
    config = {"enabled": True}
    km = KeyBackupManager(config)
    
    # Test backup with filesystem errors
    with patch('hierarchical_blockchain.security.key_backup_manager.open') as mock_open:
        mock_open.side_effect = IOError("Permission denied")

        def backup_with_error():
            try:
                km.backup_keys(b"pub", b"priv", "test")
                return False
            except (IOError, BackupError):
                return True

        result = backup_with_error()
        assert result is True

    # Test restore with missing backup file (without benchmark)
    def restore_missing():
        try:
            km.restore_keys("nonexistent_backup")
            return False
        except (FileNotFoundError, RestoreError):
            return True

    assert restore_missing() is True

def test_key_backup_manager_restore(benchmark=None):
    """Test KeyBackupManager restore with missing backup file   using benchmark"""
    config = {"enabled": True}
    km = KeyBackupManager(config)

    # Test restore with missing backup file
    def restore_missing():
        try:
            km.restore_keys("nonexistent_backup")
            return False
        except RestoreError:
            return True

    if benchmark:
        result = benchmark(restore_missing)
    else:
        result = restore_missing()

    assert result is True


def test_key_backup_manager_retention_policies():
    """Test KeyBackupManager retention policy enforcement"""
    config = {
        "enabled": True,
        "retention_period": 0  # Immediately expire
    }
    km = KeyBackupManager(config)
    
    # Mock encryption
    with (patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet):
        mock_fernet_instance = Mock()
        mock_fernet_instance.encrypt.return_value = b"encrypted_data"
        mock_fernet.return_value = mock_fernet_instance
        
        # Create backup
        backup_id = km.backup_keys(b"pub", b"priv", "retention_test")
        assert backup_id is not None

        # Because retention_period is 0, backup should be cleaned up immediately
        # So list_backups should return empty list
        def list_backups_func():
            return km.list_backups()

        result = list_backups_func()
        assert len(result) == 0  # Changed from >= 1 to == 0


def test_certificate_authority_edge_cases():
    """Test CertificateAuthority edge cases"""
    ca = CertificateAuthority(
        root_cert="test-root",
        intermediate_certs=["test-intermediate"],
        policy={"default_validity": 365}
    )

    # Test issuing certificate with very short validity
    cert = ca.issue_certificate(
        subject="short-validity-test",
        public_key="test-key",
        attributes={},
        valid_days=-1  # Already expired (negative value)
    )

    assert cert is not None
    assert cert.is_expired() is True

    def verify_expired_cert():
        return ca.verify_certificate(cert.cert_id)

    result = verify_expired_cert()
    assert result is False


def test_certificate_authority_revoke_nonexistent():
    """Test revoking non-existent certificate in CertificateAuthority"""
    ca = CertificateAuthority(
        root_cert="test-root",
        intermediate_certs=["test-intermediate"],
        policy={"default_validity": 365}
    )

    # Test revoking non-existent certificate
    def revoke_nonexistent_cert():
        return ca.revoke_certificate("non-existent-cert")

    result = revoke_nonexistent_cert()
    assert result is False


def test_organization_policies_edge_cases():
    """Test OrganizationPolicies edge cases"""
    policies = OrganizationPolicies()
    
    # Test evaluating non-existent policy
    def evaluate_nonexistent_policy():
        return policies.evaluate_policy("non-existent", {})

    result = evaluate_nonexistent_policy()
    assert result is False


def test_organization_policies_check_nonexistent_role():
    """Test checking permission for non-existent role in OrganizationPolicies"""
    policies = OrganizationPolicies()

    # Test checking permission for non-existent role
    def check_nonexistent_role():
        return policies.check_permission("non-existent-role", "read")

    result = check_nonexistent_role()
    assert result is False


def test_organization_policies_define_complex_policy():
    """Test defining policy with complex configuration in OrganizationPolicies"""
    policies = OrganizationPolicies()

    # Test defining policy with complex configuration
    complex_policy = {
        "required_attributes": ["role", "department", "clearance"],
        "conditions": {
            "department": ["engineering", "security"],
            "clearance": "high"
        },
        "version": "2.0"
    }
    
    policies.define_policy("complex_policy", complex_policy)
    assert "complex_policy" in policies.policies


def test_msp_edge_cases():
    """Test HierarchicalMSP edge cases"""
    ca_config = {
        "root_cert": "edge-test-root",
        "intermediate_certs": ["edge-test-intermediate"],
        "policy": {"default_validity": 365}
    }
    
    msp = HierarchicalMSP("edge-test-org", ca_config)
    
    # Test getting info for non-existent entity
    def get_nonexistent_entity():
        return msp.get_entity_info("non-existent")

    result = get_nonexistent_entity()
    assert result is None


def test_msp_audit_log_zero_limit():
    """Test HierarchicalMSP audit log with zero limit"""
    ca_config = {
        "root_cert": "edge-test-root",
        "intermediate_certs": ["edge-test-intermediate"],
        "policy": {"default_validity": 365}
    }

    msp = HierarchicalMSP("edge-test-org", ca_config)

    # Test audit log limit
    def get_audit_log_zero():
        return msp.get_audit_log(0)

    result = get_audit_log_zero()
    assert isinstance(result, list)


def test_msp_audit_log_negative_limit():
    """Test HierarchicalMSP audit log with negative limit"""
    ca_config = {
        "root_cert": "edge-test-root",
        "intermediate_certs": ["edge-test-intermediate"],
        "policy": {"default_validity": 365}
    }

    msp = HierarchicalMSP("edge-test-org", ca_config)

    def get_audit_log_negative():
        return msp.get_audit_log(-1)

    result = get_audit_log_negative()
    assert isinstance(result, list)


def test_msp_role_registration():
    """Test HierarchicalMSP role registration edge cases"""
    ca_config = {
        "root_cert": "edge-test-root",
        "intermediate_certs": ["edge-test-intermediate"],
        "policy": {"default_validity": 365}
    }

    msp = HierarchicalMSP("edge-test-org", ca_config)

    # Test registering entity with custom role (before defining it)
    credentials = {
        "public_key": "test-key",
        "private_key": "test-private"
    }

    def register_without_role():
        return msp.register_entity("custom-role-user", credentials, "custom_role")

    result = register_without_role()
    assert result is False  # Should fail as role doesn't exist
    
    # Define custom role and try again
    msp.define_role("custom_role", ["custom_action"], [], 90)

    def register_with_role():
        return msp.register_entity("custom-role-user", credentials, "custom_role")

    result = register_with_role()
    assert result is True  # Should now succeed


def test_msp_audit_logging_comprehensive(benchmark=None):
    """Comprehensive test of MSP audit logging"""
    ca_config = {
        "root_cert": "audit-test-root",
        "intermediate_certs": ["audit-test-intermediate"],
        "policy": {"default_validity": 365}
    }
    
    msp = HierarchicalMSP("audit-test-org", ca_config)
    credentials = {
        "public_key": "audit-key",
        "private_key": "audit-private"
    }
    
    # Perform several operations
    msp.register_entity("audit-user-1", credentials, "admin")
    msp.register_entity("audit-user-2", credentials, "viewer")
    msp.validate_identity("audit-user-1", credentials)
    msp.authorize_action("audit-user-1", "manage_entities")
    msp.revoke_entity("audit-user-2", "testing")
    
    # Check audit log
    def get_audit_log():
        return msp.get_audit_log()

    if benchmark:
        result = benchmark(get_audit_log)
    else:
        result = get_audit_log()

    assert len(result) >= 5  # At least our 5 operations

    # Check log content
    event_types = [log["event_type"] for log in result]
    assert "entity_registered" in event_types
    assert "identity_validated" in event_types
    assert "action_authorized" in event_types
    assert "entity_revoked" in event_types


def test_key_validation_none_key():
    """Test key validation with None key"""
    km = KeyManager()
    
    # Test None key
    def validate_none_key():
        return km.is_valid(None)

    result = validate_none_key()
    assert result is False


def test_key_validation_empty_key():
    """Test key validation with empty key"""
    km = KeyManager()

    # Test empty key
    def validate_empty_key():
        return km.is_valid("")

    result = validate_empty_key()
    assert result is False


def test_key_validation_short_key():
    """Test key validation with short key"""
    km = KeyManager()

    # Test short key
    def validate_short_key():
        return km.is_valid("short")

    result = validate_short_key()
    assert result is False


def test_key_validation_nonexistent_key():
    """Test key validation with nonexistent key"""
    km = KeyManager()

    # Test key with no storage backend entry
    def validate_nonexistent_key():
        return km.is_valid("nonexistentkeywithsufficientlength1234567890")

    result = validate_nonexistent_key()
    assert result is False


def test_key_validation_expired_key():
    """Test key validation with expired key"""
    km = KeyManager()

    # Test expired key
    expired_key = "expired_key_123456789012345"
    km.storage[expired_key] = {
        'user_id': 'test_user',
        'permissions': ['events'],
        'created_at': 1000,
        'expires_at': 1001  # In the past
    }

    def validate_expired_key():
        return km.is_valid(expired_key)

    result = validate_expired_key()
    assert result is False


def test_key_validation_valid_key():
    """Test key validation with valid key"""
    km = KeyManager()

    # Test valid key
    valid_key = "valid_key_123456789012345"
    km.storage[valid_key] = {
        'user_id': 'test_user',
        'permissions': ['events'],
        'created_at': time.time(),
        'expires_at': time.time() + 3600  # In the future
    }

    def validate_valid_key():
        return km.is_valid(valid_key)

    result = validate_valid_key()
    assert result is True
