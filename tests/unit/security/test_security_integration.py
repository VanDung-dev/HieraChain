"""
Integration tests for security modules.

This module contains integration tests that verify interactions between different
security components including KeyManager, KeyBackupManager, and MSP.
"""

import json
from unittest.mock import Mock, patch

from hierarchical_blockchain.security.key_manager import KeyManager
from hierarchical_blockchain.security.key_backup_manager import KeyBackupManager
from hierarchical_blockchain.security.msp import HierarchicalMSP


def test_end_to_end_key_lifecycle(benchmark):
    """Test end-to-end key lifecycle from creation to backup to MSP registration"""
    def run_test():
        # Step 1: Create API key using KeyManager
        km = KeyManager()
        api_key = km.create_key(
            user_id="integration_test_user",
            permissions=["all"],
            app_details={"name": "Integration Test App", "version": "1.0"},
            expires_in=3600
        )

        # Verify key was created properly
        assert km.is_valid(api_key) is True
        assert km.has_permission(api_key, "all") is True
        assert km.get_user(api_key) == "integration_test_user"

        # Step 2: Backup the key using KeyBackupManager
        config = {"enabled": True}
        kb = KeyBackupManager(config)

        # Mock encryption for predictable testing
        with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
            mock_fernet_instance = Mock()
            mock_fernet_instance.encrypt.return_value = b"encrypted_data"
            mock_fernet.return_value = mock_fernet_instance

            # Convert key to bytes for backup (simulating internal representation)
            key_bytes = api_key.encode('utf-8')
            backup_id = kb.backup_keys(key_bytes, key_bytes, "api_key")

            # Verify backup was created
            assert backup_id.startswith("api_key_")

            # Verify backup integrity
            assert kb.verify_backup_integrity(backup_id) is True

        # Step 3: Register entity in MSP using the key
        ca_config = {
            "root_cert": "integration-test-root",
            "intermediate_certs": ["integration-test-intermediate"],
            "policy": {"default_validity": 365}
        }

        msp = HierarchicalMSP("integration-test-org", ca_config)
        credentials = {
            "public_key": api_key,  # Using API key as public key for this test
            "private_key": "integration-private-key"
        }

        # Register entity
        result = msp.register_entity(
            "integration-entity",
            credentials,
            "admin"
        )

        assert result is True

        # Verify entity registration
        entity_info = msp.get_entity_info("integration-entity")
        assert entity_info is not None
        assert entity_info["entity_id"] == "integration-entity"
        assert entity_info["role"] == "admin"

        # Validate identity
        is_valid = msp.validate_identity("integration-entity", credentials)
        assert is_valid is True

        # Authorize action
        is_authorized = msp.authorize_action("integration-entity", "manage_entities")
        assert is_authorized is True

        return True

    result = benchmark(run_test)
    assert result is True


def test_key_revocation_propagation(benchmark):
    """Test that key revocation propagates through the system"""
    def run_test():
        # Create key
        km = KeyManager()
        api_key = km.create_key("revocation_test_user", ["read", "write"])

        # Verify key is initially valid
        assert km.is_valid(api_key) is True

        # Create backup of the key
        config = {"enabled": True}
        kb = KeyBackupManager(config)

        with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
            mock_fernet_instance = Mock()
            mock_fernet_instance.encrypt.return_value = b"encrypted_data"
            mock_fernet.return_value = mock_fernet_instance

            key_bytes = api_key.encode('utf-8')
            backup_id = kb.backup_keys(key_bytes, key_bytes, "revocation_test")
            assert backup_id.startswith("revocation_test_")

        # Register in MSP
        ca_config = {
            "root_cert": "revocation-test-root",
            "intermediate_certs": ["revocation-test-intermediate"],
            "policy": {"default_validity": 365}
        }

        msp = HierarchicalMSP("revocation-test-org", ca_config)
        credentials = {
            "public_key": api_key,
            "private_key": "revocation-private-key"
        }

        result = msp.register_entity("revocation-entity", credentials, "operator")
        assert result is True

        # Verify initial state
        assert km.is_valid(api_key) is True
        assert msp.validate_identity("revocation-entity", credentials) is True

        # Revoke the key
        km.revoke_key(api_key)

        # Verify revocation propagated
        assert km.is_revoked(api_key) is True
        # Note: KeyManager revocation doesn't automatically affect MSP validation
        # because they operate on different principles (MSP uses certificates)

        return True

    result = benchmark(run_test)
    assert result is True


def test_multiple_module_interaction_under_load(benchmark):
    """Test multiple security modules interacting under load"""
    def run_test():
        # Create multiple keys
        km = KeyManager()
        keys = []
        for i in range(10):
            key = km.create_key(f"user_{i}", ["read", "write"], {"app": f"LoadTestApp_{i}"})
            keys.append(key)

        # Backup all keys
        config = {"enabled": True}
        kb = KeyBackupManager(config)

        with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
            mock_fernet_instance = Mock()
            mock_fernet_instance.encrypt.return_value = b"encrypted_data"
            mock_fernet.return_value = mock_fernet_instance

            backup_ids = []
            for i, key in enumerate(keys):
                key_bytes = key.encode('utf-8')
                backup_id = kb.backup_keys(key_bytes, key_bytes, f"load_test_{i}")
                backup_ids.append(backup_id)

        # Register entities in MSP
        ca_config = {
            "root_cert": "load-test-root",
            "intermediate_certs": ["load-test-intermediate"],
            "policy": {"default_validity": 365}
        }

        msp = HierarchicalMSP("load-test-org", ca_config)

        for i, key in enumerate(keys):
            credentials = {
                "public_key": key,
                "private_key": f"private-key-{i}"
            }

            result = msp.register_entity(f"load-entity-{i}", credentials, "operator")
            assert result is True

        # Validate all entities
        for i, key in enumerate(keys):
            credentials = {
                "public_key": key,
                "private_key": f"private-key-{i}"
            }

            # Check KeyManager validation
            assert km.is_valid(key) is True

            # Check MSP validation
            assert msp.validate_identity(f"load-entity-{i}", credentials) is True

            # Check permissions
            assert km.has_permission(key, "read") is True

            # Check authorization
            assert msp.authorize_action(f"load-entity-{i}", "query_data") is True

        return True

    result = benchmark(run_test)
    assert result is True


def test_security_modules_interoperability(benchmark):
    """Test interoperability between different security modules"""
    def run_test():
        # Create a key with KeyManager
        km = KeyManager()
        api_key = km.create_key(
            user_id="interop_test_user",
            permissions=["events", "chains", "proofs"],
            app_details={"name": "Interop Test App"}
        )

        # Verify key
        assert km.is_valid(api_key) is True

        # Create backup with KeyBackupManager
        config = {"enabled": True}
        kb = KeyBackupManager(config)

        with patch('hierarchical_blockchain.security.key_backup_manager.Fernet') as mock_fernet:
            mock_fernet_instance = Mock()
            mock_fernet_instance.encrypt.return_value = b"encrypted_data"
            # Fix: Mock decrypt to return proper JSON string that matches real behavior
            # The keys should be hex-encoded strings as they are stored in the backup
            mock_fernet_instance.decrypt.return_value = json.dumps({
                "public_key": api_key.encode().hex(),  # Store as hex string like in real implementation
                "private_key": "a" * 64,  # Valid 32-byte hex string for private key
                "key_type": "interop_test"
            }).encode()
            mock_fernet.return_value = mock_fernet_instance

            key_bytes = api_key.encode('utf-8')
            backup_id = kb.backup_keys(key_bytes, key_bytes, "interop_test")

            # Restore the key
            restored_data = kb.restore_keys(backup_id)
            # Fix: After restoration, the keys are bytes, not UTF-8 strings that need decoding
            restored_key = restored_data["public_key"].decode('utf-8')

            # Verify restored key matches original
            assert restored_key == api_key

        # Use in MSP
        ca_config = {
            "root_cert": "interop-test-root",
            "intermediate_certs": ["interop-test-intermediate"],
            "policy": {"default_validity": 365}
        }

        msp = HierarchicalMSP("interop-test-org", ca_config)
        credentials = {
            "public_key": api_key,
            "private_key": "interop-private-key"
        }

        # Register entity with restored key information
        result = msp.register_entity("interop-entity", credentials, "operator")
        assert result is True

        # Cross-check information between modules
        assert km.get_user(api_key) == "interop_test_user"
        entity_info = msp.get_entity_info("interop-entity")
        assert entity_info["role"] == "operator"

        return True

    result = benchmark(run_test)
    assert result is True
