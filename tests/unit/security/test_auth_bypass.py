"""
Unit tests for authentication bypass prevention.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from hierachain.security.key_provider import LocalKeyProvider, KeyPair, CryptoError
from hierachain.config.settings import Settings


@pytest.fixture
def mock_missing_identity():
    """Mock identity file as missing."""
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = False
        yield mock_exists


@pytest.fixture
def mock_corrupt_identity():
    """Mock identity file as corrupt/unreadable."""
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        with patch("hierachain.security.key_provider.LocalKeyProvider.from_file") as mock_load:
            mock_load.side_effect = CryptoError("Invalid identity file")
            yield mock_load


@pytest.fixture
def valid_identity_file(tmp_path):
    """Create a valid identity file for testing."""
    identity_dir = tmp_path / "config"
    identity_dir.mkdir()
    
    kp = KeyPair.generate()
    
    identity_file = identity_dir / "identity.json"
    import json
    identity_file.write_text(json.dumps({
        "public_key": kp.public_key,
        "private_key": kp.private_key
    }))
    
    return str(identity_file)


def test_ephemeral_key_not_allowed_when_identity_missing(mock_missing_identity):
    """Verify that system rejects access when identity file is missing."""
    from hierachain.api.v3 import endpoints
    
    with pytest.raises(HTTPException) as exc_info:
        endpoints.get_current_key_provider()
    
    assert exc_info.value.status_code == 401
    assert "identity" in exc_info.value.detail.lower() or "configured" in exc_info.value.detail.lower()


def test_auth_bypass_v3_endpoints_reject_unauthenticated(mock_missing_identity):
    """Test that v3 endpoints properly reject unauthenticated requests."""
    from hierachain.api.v3 import endpoints
    
    with pytest.raises(HTTPException) as exc_info:
        endpoints.get_current_key_provider()
    
    assert exc_info.value.status_code == 401


def test_corrupt_identity_file_rejected(mock_corrupt_identity):
    """Test that corrupt identity files are rejected with 401."""
    from hierachain.api.v3 import endpoints
    
    with pytest.raises(HTTPException) as exc_info:
        endpoints.get_current_key_provider()
    
    assert exc_info.value.status_code == 401


def test_valid_identity_loads_successfully(valid_identity_file):
    """Test that valid identity files are loaded correctly."""
    with patch("hierachain.api.v3.endpoints.get_settings") as mock_settings:
        mock_s = MagicMock()
        mock_s.VALIDATOR_IDENTITY_PATH = valid_identity_file
        mock_settings.return_value = mock_s
        
        from hierachain.api.v3 import endpoints
        provider = endpoints.get_current_key_provider()
        
        assert provider is not None
        assert provider.public_key_hex is not None


def test_ephemeral_key_can_sign():
    """Verify ephemeral keys can still sign."""
    kp = KeyPair.generate()
    ephemeral_provider = LocalKeyProvider(kp)
    
    test_message = b"test message"
    signature = ephemeral_provider.sign(test_message)
    
    assert signature is not None


def test_identity_path_not_exists_raises_error(tmp_path):
    """Test that non-existent identity path properly raises error."""
    fake_path = tmp_path / "nonexistent" / "identity.json"
    
    from hierachain.api.v3 import endpoints
    
    with patch.object(endpoints, 'get_settings') as mock_settings:
        mock_s = MagicMock()
        mock_s.VALIDATOR_IDENTITY_PATH = str(fake_path)
        mock_settings.return_value = mock_s
        
        with pytest.raises(HTTPException) as exc_info:
            endpoints.get_current_key_provider()
        
        assert exc_info.value.status_code == 401


def test_identity_load_failure_propagates_error():
    """Test that failures in loading identity propagate as 401."""
    from hierachain.api.v3 import endpoints
    
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        
        with patch("hierachain.security.key_provider.LocalKeyProvider.from_file") as mock_load:
            mock_load.side_effect = CryptoError("Decryption failed")
            
            with pytest.raises(HTTPException) as exc_info:
                endpoints.get_current_key_provider()
            
            assert exc_info.value.status_code == 401