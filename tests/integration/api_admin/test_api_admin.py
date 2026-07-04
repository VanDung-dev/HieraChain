"""
Test script for HieraChain API admin (System & Admin)

This script tests the new admin endpoints:
- POST /api/admin/verify-identity
- GET /api/admin/status

Prerequisites:
1. Install hrc-core: maturin develop --release --manifest-path hrc-core/Cargo.toml
2. Start the API server first (in another terminal)
"""

import requests
import json
import os
# from pathlib import Path

# API Base URL
BASE_URL = "http://127.0.0.1:2661"


def _post_and_print(path: str, payload: dict):
    try:
        response = requests.post(
            f"{BASE_URL}{path}",
            json=payload,
            timeout=5,
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to server. Make sure the API server is running.")
    except Exception as e:
        print(f"ERROR: {e}")


def test_node_status():
    """Test GET /admin/status endpoint"""
    print("\n" + "="*50)
    print("TEST: GET /admin/status")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/api/admin/status", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to server. Make sure the API server is running.")
    except Exception as e:
        print(f"ERROR: {e}")


def test_verify_identity(challenge: str = "abcd1234"):
    """Test POST /admin/verify-identity endpoint"""
    print("\n" + "="*50)
    print("TEST: POST /admin/verify-identity")
    print("="*50)
    
    # Challenge must be hex-encoded
    challenge_hex = challenge.encode().hex()
    print(f"Challenge (raw): {challenge}")
    print(f"Challenge (hex): {challenge_hex}")
    
    payload = {"challenge": challenge_hex}
    
    _post_and_print("/api/admin/verify-identity", payload)


def test_inject_license(license_key: str = None):
    """Test POST /admin/inject-license endpoint"""
    print("\n" + "="*50)
    print("TEST: POST /admin/inject-license")
    print("="*50)
    
    # Try to get license from environment if not provided
    if license_key is None:
        license_key = os.environ.get("HIERACHAIN_LICENSE_KEY")
        if license_key:
            print(f"Using license from environment variable")
        else:
            print("WARNING: No license key provided and HIERACHAIN_LICENSE_KEY not set")
            print("Skipping inject-license test")
            return
    
    payload = {"license_key": license_key}
    print(f"License Key (first 20 chars): {license_key[:20]}...")
    
    _post_and_print("/api/admin/inject-license", payload)


def test_license_module():
    """Test LicenseManager functions directly via Python bindings"""
    print("\n" + "="*50)
    print("TEST: Direct hrc_core LicenseManager test")
    print("="*50)
    
    try:
        import hrc_core
        print(f"hrc_core version: {hrc_core.__version__}")
        print("SUCCESS: hrc_core imported successfully!")
    except ImportError as e:
        print(f"ERROR: Cannot import hrc_core: {e}")
        print("Make sure to run: maturin develop --release --manifest-path hrc-core/Cargo.toml")
    except Exception as e:
        print(f"ERROR: {e}")


def main():
    """Run all tests"""
    print("="*60)
    print("HieraChain API admin Test Suite")
    print("="*60)
    
    # Test 1: Try to import hrc_core
    test_license_module()
    
    # Test 2: Node status
    test_node_status()
    
    # Test 3: Verify identity
    test_verify_identity("test_challenge_123")
    
    print("\n" + "="*60)
    print("Tests completed!")
    print("="*60)


if __name__ == "__main__":
    main()
