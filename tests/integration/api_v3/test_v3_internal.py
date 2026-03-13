"""
Test suite for the Hierachain API v3 internal endpoints.
"""

from fastapi.testclient import TestClient
from hierachain.api import app

client = TestClient(app)

def test_verify_identity():
    """Test POST /api/v3/verify-identity endpoint"""
    print("\nTEST: POST /api/v3/verify-identity")
    
    challenge = "abcd1234"
    payload = {"challenge": challenge}
    
    response = client.post("/api/v3/verify-identity", json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["challenge"] == challenge
    assert "signature" in data
    assert "node_id" in data

def test_node_status():
    """Test GET /api/v3/status endpoint"""
    print("\nTEST: GET /api/v3/status")
    
    response = client.get("/api/v3/status")
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert "version" in data
    assert "uptime" in data
    assert "chains_active" in data
