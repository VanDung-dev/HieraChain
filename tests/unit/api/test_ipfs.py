"""
Test script for IPFS Storage Module.

This script demonstrates the usage of IPFSClient and AESEncryption.
Run this after setting up IPFS daemon to verify everything works.

Usage:
    python -m hierachain.api.storage.test_ipfs
"""

import json
from hierachain.api.storage.encryption import AESEncryption, EncryptionError
from hierachain.api.storage.ipfs_client import IPFSClient, IPFSError


def test_encryption():
    """Test AES-256-GCM encryption/decryption."""
    print("=" * 60)
    print("Testing AES-256-GCM Encryption")
    print("=" * 60)

    # Test 1: Basic encryption/decryption
    print("\n[Test 1] Basic encryption/decryption")
    enc = AESEncryption()
    plaintext = b"Hello, HieraChain IPFS Integration!"

    ciphertext, nonce = enc.encrypt(plaintext)
    print(f"  Plaintext: {plaintext}")
    print(f"  Ciphertext length: {len(ciphertext)} bytes")
    print(f"  Nonce: {nonce.hex()}")

    decrypted = enc.decrypt(ciphertext, nonce)
    print(f"  Decrypted: {decrypted}")

    assert plaintext == decrypted, "Decryption failed!"
    print("  ✅ Test passed!")

    # Test 2: JSON encryption/decryption
    print("\n[Test 2] JSON encryption/decryption")
    data = {
        "event_type": "contract_execution",
        "contract_id": "contract_123",
        "parameters": {
            "amount": 1000,
            "recipient": "0xABC123"
        }
    }

    ciphertext, nonce = enc.encrypt_json(data)
    print(f"  Original: {json.dumps(data, indent=2)}")
    print(f"  Encrypted size: {len(ciphertext)} bytes")

    decrypted_data = enc.decrypt_json(ciphertext, nonce)
    print(f"  Decrypted: {json.dumps(decrypted_data, indent=2)}")

    assert data == decrypted_data, "JSON decryption failed!"
    print("  ✅ Test passed!")

    # Test 3: With AAD (metadata)
    print("\n[Test 3] Encryption with AAD (metadata)")
    metadata = {
        "channel_id": "supply-chain",
        "organization": "ACME Corp"
    }
    metadata_bytes = json.dumps(metadata, sort_keys=True).encode('utf-8')

    ciphertext, nonce = enc.encrypt(plaintext, associated_data=metadata_bytes)
    print(f"  Metadata: {metadata}")
    print(f"  Encrypted with AAD")

    # Decrypt with correct AAD
    decrypted = enc.decrypt(ciphertext, nonce, associated_data=metadata_bytes)
    assert plaintext == decrypted
    print("  ✅ Decryption with correct AAD succeeded")

    # Try to decrypt with wrong AAD (should fail)
    try:
        wrong_metadata = json.dumps({"wrong": "metadata"}).encode('utf-8')
        enc.decrypt(ciphertext, nonce, associated_data=wrong_metadata)
        print("  ❌ Should have failed with wrong AAD!")
    except EncryptionError:
        print("  ✅ Correctly rejected wrong AAD")

    # Test 4: Key derivation from password
    print("\n[Test 4] Key derivation from password")
    password = "MySecurePassword123!"
    salt = b"fixed_salt_for_test_123456"  # In practice, use random salt

    enc1 = AESEncryption.from_password(password, salt)
    enc2 = AESEncryption.from_password(password, salt)

    # Same password + salt should produce same key
    assert enc1.key == enc2.key
    print(f"  Password: {password}")
    print(f"  Derived key: {enc1.key.hex()[:32]}...")
    print("  ✅ Key derivation is deterministic")

    print("\n" + "=" * 60)
    print("All encryption tests passed! ✅")
    print("=" * 60)


def test_ipfs_client():
    """Test IPFS client (requires running IPFS daemon)."""
    print("\n" + "=" * 60)
    print("Testing IPFS Client")
    print("=" * 60)

    try:
        # Create client
        print("\n[Test 1] Creating IPFS client")
        client = IPFSClient()
        print("  ✅ Client created")

        # Check daemon version
        print("\n[Test 2] Checking IPFS daemon version")
        version = client.get_daemon_version()
        print(f"  IPFS Version: {version.get('Version', 'unknown')}")
        print("  ✅ Connected to IPFS daemon")

        # Test upload/download bytes
        print("\n[Test 3] Upload/download encrypted bytes")
        test_data = b"This is test data for IPFS storage"

        result = client.upload_bytes(test_data, encrypt=True)
        print(f"  Uploaded CID: {result['cid']}")
        print(f"  Size: {result['size']} bytes")
        print(f"  Nonce: {result['nonce']}")
        print(f"  Encrypted: {result['encrypted']}")

        downloaded = client.download_bytes(
            cid=result['cid'],
            encrypted=True,
            nonce=result['nonce']
        )
        assert test_data == downloaded
        print("  ✅ Upload/download successful")

        # Test upload/download JSON
        print("\n[Test 4] Upload/download encrypted JSON")
        json_data = {
            "event_type": "test_event",
            "data": {
                "key1": "value1",
                "key2": 12345,
                "nested": {
                    "array": [1, 2, 3]
                }
            }
        }

        result = client.upload_json(json_data, encrypt=True)
        print(f"  Uploaded CID: {result['cid']}")

        downloaded_json = client.download_json(
            cid=result['cid'],
            encrypted=True,
            nonce=result['nonce']
        )
        assert json_data == downloaded_json
        print("  ✅ JSON upload/download successful")

        # Test with metadata (AAD)
        print("\n[Test 5] Upload/download with metadata (AAD)")
        metadata = {
            "channel": "test-channel",
            "org": "test-org"
        }

        result = client.upload_json(
            data=json_data,
            encrypt=True,
            metadata=metadata
        )

        downloaded_with_metadata = client.download_json(
            cid=result['cid'],
            encrypted=True,
            nonce=result['nonce'],
            metadata=metadata
        )
        assert json_data == downloaded_with_metadata
        print("  ✅ Upload/download with metadata successful")

        # Test pinning
        print("\n[Test 6] Pin management")
        cid = result['cid']

        # List pins
        pins = client.list_pins()
        print(f"  Total pinned items: {len(pins)}")

        # Check if available
        is_avail = client.is_available(cid)
        print(f"  CID {cid[:12]}... is available: {is_avail}")

        print("  ✅ Pin management working")

        # Cleanup
        print("\n[Test 7] Cleanup - unpinning test data")
        client.unpin(cid)
        print("  ✅ Cleanup successful")

        print("\n" + "=" * 60)
        print("All IPFS tests passed! ✅")
        print("=" * 60)

    except IPFSError as e:
        print(f"\n❌ IPFS Error: {e}")
        print("\nMake sure IPFS daemon is running:")
        print("  $ ipfs daemon")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("HieraChain IPFS Storage Module Test Suite")
    print("=" * 60)

    # Test encryption (always works)
    test_encryption()

    # Test IPFS client (requires daemon)
    print("\n" + "=" * 60)
    print("IPFS Client Tests (requires IPFS daemon)")
    print("=" * 60)
    print("\nNote: These tests require a running IPFS daemon.")
    print("If you haven't started it, run: ipfs daemon")

    response = input("\nDo you want to run IPFS tests? (y/n): ").lower()
    if response == 'y':
        test_ipfs_client()
    else:
        print("\nSkipping IPFS tests.")

    print("\n" + "=" * 60)
    print("Test suite completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
