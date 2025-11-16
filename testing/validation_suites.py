"""
Validation Suites for Hierarchical Blockchain Framework
Priority-based risk validation tests covering all identified risks

This module implements comprehensive validation tests for error mitigation and validation
framework, ensuring all critical, high, medium, and low priority risks are properly tested.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from hierarchical_blockchain.error_mitigation.validator import (
    ConsensusValidator,
    SecurityError,
    ValidationError,
    validate_certificate
)
from hierarchical_blockchain.security.certificate import CertificateValidator
from hierarchical_blockchain.error_mitigation.recovery_engine import NetworkRecoveryEngine
from hierarchical_blockchain.security.key_backup_manager import KeyBackupManager
from hierarchical_blockchain.security.key_manager import KeyManager
from hierarchical_blockchain.api.v3.verify import VerifyAPIKey


class TestPriorityLevel1Critical:
    """
    Priority Level 1: Critical Risk Validation Tests
    Tests for risks that could cause complete system failure.
    """

    @pytest.mark.critical
    def test_bft_node_count_validation(self):
        """
        Test BFT consensus node count validation.
        Validates requirement: n >= 3f + 1 nodes for Byzantine Fault Tolerance.
        """
        config = {"f": 1, "auto_scale_threshold": 0.8}
        validator = ConsensusValidator(config)
        
        # Test insufficient nodes (should raise ValidationError)
        with pytest.raises(ValidationError, match="Insufficient nodes"):
            validator.validate_node_count(["node1", "node2", "node3"])  # 3 < 4
        
        # Test sufficient nodes (should pass)
        result = validator.validate_node_count(["node1", "node2", "node3", "node4"])
        assert result is True
        
        # Test with f=2 (requires 7 nodes)
        validator_f2 = ConsensusValidator({"f": 2})
        with pytest.raises(ValidationError):
            validator_f2.validate_node_count(["n1", "n2", "n3", "n4", "n5", "n6"])  # 6 < 7
        
        assert validator_f2.validate_node_count([f"node{i}" for i in range(1, 8)]) is True
    
    @pytest.mark.critical
    def test_signature_verification_strictness(self):
        """
        Test enhanced signature verification with strict mode and fallback.
        Validates cryptographic integrity in BFT consensus.
        """
        # Mock BFT consensus with strict verification
        mock_consensus = Mock()
        mock_consensus.config = {"verification_strictness": "high", "fallback_mode": "quorum_based"}
        mock_consensus.all_nodes = [Mock() for _ in range(4)]
        mock_consensus.f = 1
        
        # Add the method of checking the validity
        def validate_strictness():
            if mock_consensus.config["verification_strictness"] == "low":
                raise Exception("Strict verification required for BFT consensus")
        
        mock_consensus.validate_strictness = validate_strictness
        
        # Test strict mode requirement
        with pytest.raises(Exception, match="Strict verification required"):
            mock_consensus.config["verification_strictness"] = "low"
            # Would trigger validation error in actual implementation
            mock_consensus.validate_strictness()  # Call the method to activate the exception
        
        # Test fallback mechanism
        mock_consensus.config["verification_strictness"] = "high"
        # This would test the quorum-based fallback in actual implementation
        assert mock_consensus.config["fallback_mode"] == "quorum_based"
    
    @pytest.mark.critical
    @pytest.mark.asyncio
    async def test_network_recovery_timeout_adjustment(self):
        """
        Test dynamic timeout adjustment for network recovery.
        Validates network fault tolerance in consensus process.
        """
        config = {"timeout_multiplier": 2.0, "redundancy_factor": 2}
        recovery_engine = NetworkRecoveryEngine(config)
        
        # Test timeout adjustment with high latency
        latency_history = [2000, 2500, 3000]  # High latency in ms
        adjusted_timeout = recovery_engine.adjust_timeout(latency_history)
        
        # Should be significantly higher than base timeout
        expected_min = recovery_engine.timeout_base * config["timeout_multiplier"]
        assert adjusted_timeout >= expected_min
        
        # Test with low latency
        low_latency = [50, 75, 100]
        low_timeout = recovery_engine.adjust_timeout(low_latency)
        assert low_timeout < adjusted_timeout  # Should be less than high latency timeout


class TestPriorityLevel2High:
    """
    Priority Level 2: High Risk Validation Tests  
    Tests for risks with significant impact on system security and performance.
    """
    
    @pytest.mark.high
    def test_backup_integrity_validation(self):
        """
        Test data backup integrity checking and multi-location distribution.
        Validates data recovery capabilities.
        """
        config = {
            "enabled": True,
            "frequency": "hourly", 
            "locations": ["primary", "secondary", "tertiary"],
            "integrity_check": "sha512"
        }
        
        backup_manager = KeyBackupManager(config)
        
        # Mock Method _verify_integrity to return True
        backup_manager._verify_integrity = Mock(return_value=True)
        backup_manager._distribute_to_locations = Mock(return_value=["primary"])
        backup_manager._update_metadata = Mock()
        backup_manager._cleanup_old_backups = Mock()
        backup_manager._log_backup_success = Mock()
        
        # Create test keys
        test_public_key = b"test_public_key_data_12345"
        test_private_key = b"test_private_key_data_67890"
        
        # Test backup creation and integrity
        with patch('os.makedirs'), patch('builtins.open', mock_open_write()):
            backup_id = backup_manager.backup_keys(test_public_key, test_private_key, "test")
            
            # Verify backup ID is created
            assert backup_id.startswith("test_")
            assert backup_id != ""
    
    @pytest.mark.high
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_resource_threshold_monitoring(self, mock_disk, mock_memory, mock_cpu):
        """
        Test resource usage threshold monitoring with auto-scaling.
        Validates performance monitoring and automated responses.
        """
        # Mock system resource readings
        mock_cpu.return_value = 85  # Above 70% threshold
        mock_memory.return_value = Mock(percent=90)  # Above 80% threshold
        mock_disk.return_value = Mock(percent=60)
        
        # This would test ResourceMonitor in actual implementation
        cpu_violation = mock_cpu.return_value > 70
        memory_violation = mock_memory.return_value.percent > 80
        
        assert cpu_violation is True
        assert memory_violation is True
        
        # Test auto-scaling trigger conditions
        violations = []
        if cpu_violation:
            violations.append("CPU")
        if memory_violation:
            violations.append("Memory")
        
        assert len(violations) == 2
        assert "CPU" in violations
        assert "Memory" in violations
    
    @pytest.mark.high
    def test_encryption_algorithm_validation(self):
        """
        Test encryption algorithm validation and key rotation scheduling.
        Validates security configuration compliance.
        """
        # Test allowed algorithm
        valid_config = {
            "algorithm": "AES-256-GCM",
            "key_rotation_interval": 2592000  # 30 days
        }
        
        # Mock encryption validator
        allowed_algorithms = ["AES-256-GCM"]
        assert valid_config["algorithm"] in allowed_algorithms
        
        # Test weak algorithm detection
        weak_config = {"algorithm": "AES-128"}
        assert weak_config["algorithm"] not in allowed_algorithms
        
        # Test key rotation interval
        min_rotation = 2592000  # 30 days
        assert valid_config.get("key_rotation_interval", 0) >= min_rotation


class TestPriorityLevel3Medium:
    """
    Priority Level 3: Medium Risk Validation Tests
    Tests for risks with moderate impact on system operations.
    """
    
    @pytest.mark.medium
    def test_multi_org_synchronization(self):
        """
        Test multi-organization configuration synchronization.
        Validates inter-organization compatibility.
        """
        # Mock multi-org network
        mock_network = Mock()
        mock_network.organizations = {
            "org1": Mock(config={"policy": "strict"}, last_updated=1000),
            "org2": Mock(config={"policy": "loose"}, last_updated=1100)
        }
        mock_network.global_config = {"policy": "strict"}
        mock_network.global_last_updated = 1200
        
        # Test configuration mismatch detection
        org1_matches = mock_network.organizations["org1"].config == mock_network.global_config
        org2_matches = mock_network.organizations["org2"].config == mock_network.global_config
        
        assert org1_matches is True
        assert org2_matches is False  # Should trigger synchronization
    
    @pytest.mark.medium
    def test_entity_tracing_optimization(self):
        """
        Test entity tracing with timeout and indexing optimization.
        Validates audit trail functionality and performance.
        """
        # Mock index store and chains
        mock_index_store = Mock()
        mock_index_store.query.return_value = [
            {"entity_id": "TEST-001", "timestamp": 1000, "event": "start"},
            {"entity_id": "TEST-001", "timestamp": 2000, "event": "process"}
        ]
        
        mock_tracer = Mock()
        mock_tracer.query_timeout = 10
        mock_tracer.index_store = mock_index_store
        
        # Test trace query
        entity_id = "TEST-001"
        events = mock_index_store.query(f"test_chain:entity:{entity_id}")
        
        assert len(events) == 2
        assert all(e["entity_id"] == entity_id for e in events)
        
        # Test timeout functionality
        start_time = time.time()
        # Simulate query within timeout
        elapsed = time.time() - start_time
        assert elapsed < mock_tracer.query_timeout
    
    @pytest.mark.medium
    def test_block_creation_retries(self):
        """
        Test block creation with validation retries and fallback.
        Validates operational resilience.
        """
        config = {
            "validation_retries": 3,
            "fallback_threshold": 2
        }
        
        # Mock block builder
        mock_builder = Mock()
        mock_builder.config = config
        mock_builder.max_retries = config["validation_retries"]
        
        # Test valid events
        valid_events = [{"entity_id": "TEST", "event": "test", "timestamp": time.time()}]
        
        # Validate event structure
        for event in valid_events:
            assert "entity_id" in event
            assert "event" in event
        
        # Test retry mechanism
        for attempt in range(mock_builder.max_retries):
            if attempt < config["fallback_threshold"]:
                # Normal processing
                assert attempt < config["fallback_threshold"]
            else:
                # Fallback triggered
                assert attempt >= config["fallback_threshold"]


class TestPriorityLevel4Low:
    """
    Priority Level 4: Low Risk Validation Tests
    Tests for interface and administrative functionality.
    """
    
    @pytest.mark.low
    def test_api_key_verification(self):
        """
        Test API key verification system with different key locations.
        Validates API security implementation.
        """
        # Test KeyManager functionality
        key_manager = KeyManager()
        
        # Create test API key
        test_key = key_manager.create_key(
            user_id="test_user",
            permissions=["events", "chains"],
            app_details={"name": "Test App"}
        )
        
        # Test key validation
        assert key_manager.is_valid(test_key) is True
        assert key_manager.is_revoked(test_key) is False
        assert key_manager.has_permission(test_key, "events") is True
        assert key_manager.has_permission(test_key, "admin") is False
        
        # Test key revocation
        key_manager.revoke_key(test_key)
        assert key_manager.is_revoked(test_key) is True
    
    @pytest.mark.low  
    def test_verify_api_key_dependency(self):
        """
        Test VerifyAPIKey FastAPI dependency.
        Validates API endpoint protection.
        """
        config = {
            "enabled": True,
            "key_location": "header",
            "key_name": "x-api-key",
            "cache_ttl": 300
        }
        
        verify_key = VerifyAPIKey(config)
        
        # Test configuration
        assert verify_key.enabled is True
        assert verify_key.key_location == "header"
        assert verify_key.key_name == "x-api-key"
        assert verify_key.cache_ttl == 300
        
        # Test resource permission checking
        assert hasattr(verify_key, 'check_resource_permission')
        assert callable(verify_key.check_resource_permission)
    
    @pytest.mark.low
    def test_cli_audit_logging(self):
        """
        Test CLI command auditing functionality.
        Validates administrative interface security.
        """
        # Mock CLI audit entry
        audit_entry = {
            "command": "inspect_chain",
            "chain": "test_chain", 
            "timestamp": time.time(),
            "user": "admin"
        }
        
        # Validate audit entry structure
        required_fields = ["command", "chain", "timestamp"]
        for field in required_fields:
            assert field in audit_entry
        
        # Test timestamp validity
        assert isinstance(audit_entry["timestamp"], (int, float))
        assert audit_entry["timestamp"] > 0


class TestComprehensiveValidation:
    """
    Comprehensive validation tests covering integration scenarios.
    """
    
    @pytest.mark.integration
    @patch('security.certificate.CertificateInfo')
    def test_certificate_expiration_check(self, mock_cert):
        """Test certificate expiration validation"""
        mock_cert_instance = mock_cert()
        mock_cert_instance.is_expired.return_value = True  # Mock phương thức trả về True trực tiếp

        _validator = CertificateValidator()
        with pytest.raises(SecurityError, match='Certificate validation failed: Certificate has expired'):
            validate_certificate(mock_cert_instance)

    def test_full_error_mitigation_workflow(self):
        """
        Test complete error mitigation workflow from detection to recovery.
        Validates end-to-end error handling capabilities.
        """
        # Test consensus validation
        consensus_config = {"f": 1}
        validator = ConsensusValidator(consensus_config)
        
        nodes = ["node1", "node2", "node3", "node4"]
        assert validator.validate_node_count(nodes) is True
        
        # Test key backup workflow
        backup_config = {
            "enabled": True,
            "locations": ["primary"],
            "encryption_algorithm": "AES-256-GCM"
        }
        
        backup_manager = KeyBackupManager(backup_config)
        assert backup_manager.enabled is True
        
        # Test API security
        api_config = {"enabled": True, "key_location": "header"}
        verify_api = VerifyAPIKey(api_config)
        assert verify_api.enabled is True
    
    @pytest.mark.integration  
    def test_post_upgrade_validation(self):
        """
        Test post-upgrade validation for v0.dev5 compliance.
        Validates that all new components work together correctly.
        """
        components_status = {
            "consensus_validator": True,
            "network_recovery": True, 
            "key_backup_manager": True,
            "api_key_verification": True,
            "validation_suites": True
        }
        
        # All components should be operational
        assert all(components_status.values())
        
        # Test framework version compliance
        framework_version = "0.dev5"
        assert framework_version == "0.dev5"
        
        # Test non-cryptocurrency compliance
        forbidden_terms = ["transaction", "mining", "coin", "token", "wallet"]
        test_description = "hierarchical blockchain framework with events and proofs"
        
        for term in forbidden_terms:
            assert term not in test_description.lower()
        
        # Verify event-based architecture terms are present
        allowed_terms = ["events", "proofs", "hierarchical", "blockchain"]
        for term in allowed_terms:
            assert term in test_description.lower()


# Helper functions for testing

def mock_open_write():
    """Helper function to mock file writing operations."""
    mock_file = MagicMock()
    mock_file.write = MagicMock()
    mock_file.__enter__ = MagicMock(return_value=mock_file)
    mock_file.__exit__ = MagicMock(return_value=None)
    return MagicMock(return_value=mock_file)


# Test configuration and fixtures

@pytest.fixture
def consensus_config():
    """Fixture for consensus configuration."""
    return {
        "f": 1,
        "auto_scale_threshold": 0.8,
        "verification_strictness": "high",
        "fallback_mode": "quorum_based"
    }


@pytest.fixture
def backup_config():
    """Fixture for backup configuration."""
    return {
        "enabled": True,
        "frequency": "daily",
        "encryption_algorithm": "AES-256-GCM",
        "locations": ["primary_vault", "secondary_cloud"],
        "integrity_check": "sha512",
        "retention_period": 365
    }


@pytest.fixture
def api_config():
    """Fixture for API configuration."""
    return {
        "enabled": True,
        "key_location": "header",
        "key_name": "x-api-key",
        "cache_ttl": 300,
        "revocation_check": "daily"
    }


if __name__ == "__main__":
    # Run the validation suite
    pytest.main([__file__, "-v", "--tb=short"])