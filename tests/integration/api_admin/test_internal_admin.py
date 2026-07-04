"""
Test suite for the Hierachain API admin internal endpoints.
"""

import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from hierachain.api import app
from hierachain.security.key_provider import LocalKeyProvider

client = TestClient(app)

def test_verify_identity():
    """Test POST /api/admin/verify-identity endpoint"""
    print("\nTEST: POST /api/admin/verify-identity")
    
    # Create a temporary identity file for testing
    key_provider = LocalKeyProvider.generate()
    
    # Create identity JSON manually (LocalKeyProvider doesn't have save method)
    identity_data = {
        "private_key": key_provider._keypair.private_key,
        "public_key": key_provider._keypair.public_key,
        "node_id": f"test-node-{os.urandom(4).hex()}"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(identity_data, f)
        temp_identity_path = f.name
    
    try:
        # Mock os.path.exists to return True for our temp path
        original_exists = os.path.exists
        
        def mock_exists(path):
            if path == temp_identity_path:
                return True
            return original_exists(path)
        
        with patch('os.path.exists', side_effect=mock_exists):
            # Also patch get_settings to return our temp path
            from hierachain.api.admin import endpoints as admin_endpoints
            mock_settings = MagicMock()
            mock_settings.VALIDATOR_IDENTITY_PATH = temp_identity_path
            mock_settings.NODE_ID = identity_data["node_id"]
            
            with patch.object(admin_endpoints, 'get_settings', return_value=mock_settings):
                challenge = "abcd1234"
                payload = {"challenge": challenge}
                
                response = client.post("/api/admin/verify-identity", json=payload)
                
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.json()}")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["challenge"] == challenge
                assert "signature" in data
                assert "node_id" in data
    finally:
        # Cleanup
        if os.path.exists(temp_identity_path):
            os.unlink(temp_identity_path)


def test_verify_identity_no_identity():
    """Test POST /api/admin/verify-identity without identity returns 401"""
    print("\nTEST: POST /api/admin/verify-identity (no identity)")
    
    # Set invalid identity path
    from hierachain.config.settings import get_settings
    settings = get_settings()
    original_path = settings.VALIDATOR_IDENTITY_PATH
    settings.VALIDATOR_IDENTITY_PATH = "/nonexistent/path/identity.json"
    
    challenge = "abcd1234"
    payload = {"challenge": challenge}
    
    response = client.post("/api/admin/verify-identity", json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 401
    
    # Restore original path
    settings.VALIDATOR_IDENTITY_PATH = original_path

def test_node_status():
    """Test GET /api/admin/status endpoint"""
    print("\nTEST: GET /api/admin/status")
    
    response = client.get("/api/admin/status")
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert "version" in data
    assert "uptime" in data
    assert "chains_active" in data
