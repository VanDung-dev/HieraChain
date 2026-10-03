"""Behavioral validation of quorum size, API keys and certificate expiry."""

import pytest
from unittest.mock import Mock

from hierachain.error_mitigation import (
    ConsensusValidator,
    SecurityError,
    ValidationError,
    validate_certificate
)
from hierachain.security import (
    KeyManager
)


@pytest.mark.critical
def test_bft_node_count_validation():
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


@pytest.mark.low
def test_api_key_verification():
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


@pytest.mark.integration
def test_certificate_expiration_check():
    """Test certificate expiration validation"""
    mock_cert = Mock()
    mock_cert.is_expired.return_value = True

    with pytest.raises(SecurityError, match='Certificate validation failed: Certificate has expired'):
        validate_certificate(mock_cert)
