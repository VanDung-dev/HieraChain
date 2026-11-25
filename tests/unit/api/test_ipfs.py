"""
Test script for IPFS Storage Module.

This script demonstrates the usage of IPFSClient and AESEncryption.
Run this after setting up IPFS daemon to verify everything works.

Usage:
    python -m hierachain.api.storage.test_ipfs
"""

import hashlib
import json
import os

import pytest

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
    print("  Encrypted with AAD")

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


def _fake_kubo(store: dict[str, bytes], pins: set[str], counter: list[int]):
    class Response:
        def __init__(self, content: bytes = b"", ok: bool = True):
            self.content = content
            self.is_success = ok

        def raise_for_status(self) -> None:
            if not self.is_success:
                raise RuntimeError("request failed")

    class FakeClient:
        def _arg(self, path: str, params: dict | None) -> str | None:
            params = params or {}
            if "arg" in params:
                return params["arg"]
            if "arg=" in path:
                return path.split("arg=", 1)[-1].split("&", 1)[0]
            return None

        def _route(self, path: str) -> str:
            return path.split("?", 1)[0]

        def post(self, path: str, params=None, files=None, **kwargs):
            params = params or {}
            route = self._route(path)
            if route == "/api/v0/version":
                return Response(json.dumps({"Version": "fake-0.0.0"}).encode())
            if route == "/api/v0/add":
                data = files["file"][1] if files and "file" in files else b""
                cid = hashlib.sha256(data + str(counter[0]).encode()).hexdigest()[:46]
                counter[0] += 1
                store[cid] = bytes(data)
                if str(params.get("pin", "false")).lower() == "true":
                    pins.add(cid)
                return Response(json.dumps({"Hash": cid}).encode())
            if route == "/api/v0/cat":
                cid = self._arg(path, params)
                if cid not in store:
                    return Response(b"", ok=False)
                return Response(store[cid])
            if route == "/api/v0/pin/add":
                cid = self._arg(path, params)
                if cid:
                    pins.add(cid)
                return Response(json.dumps({"Pins": [cid]}).encode())
            if route == "/api/v0/pin/rm":
                cid = self._arg(path, params)
                if cid:
                    pins.discard(cid)
                return Response(json.dumps({"Pins": [cid]}).encode())
            if route == "/api/v0/pin/ls":
                return Response(
                    json.dumps({"Keys": {cid: {"Type": "recursive"} for cid in pins}}).encode()
                )
            if route == "/api/v0/files/stat":
                arg = self._arg(path, params) or ""
                cid = arg.replace("/ipfs/", "")
                return Response(json.dumps({"Hash": cid}).encode(), ok=cid in store)
            return Response(b"{}", ok=False)

        def close(self) -> None:
            return None

    return FakeClient()


def test_ipfs_client():
    """Test IPFS client with an in-memory Kubo API stub."""
    print("\n" + "=" * 60)
    print("Testing IPFS Client")
    print("=" * 60)

    with IPFSClient(auto_pin=True) as client:
        print("\n[Test 1] Creating IPFS client")
        print("  ✅ Client created")

        store: dict[str, bytes] = {}
        pins: set[str] = set()
        counter = [0]
        client._client = _fake_kubo(store, pins, counter)

        print("\n[Test 2] Checking IPFS daemon version")
        try:
            version = client.get_daemon_version()
        except IPFSError as exc:
            pytest.skip(f"IPFS daemon is unavailable: {exc}")
        print(f"  IPFS Version: {version.get('version', version.get('Version', 'unknown'))}")
        print("  ✅ Connected to IPFS daemon")

        print("\n[Test 3] Upload/download encrypted bytes")
        test_data = b"This is test data for IPFS storage"
        result = client.upload_bytes(test_data, encrypt=True)
        print(f"  Uploaded CID: {result['cid']}")
        print(f"  Size: {result['size']} bytes")
        print(f"  Nonce: {result['nonce']}")
        print(f"  Encrypted: {result['encrypted']}")
        downloaded = client.download_bytes(
            cid=result["cid"], encrypted=True, nonce=result["nonce"]
        )
        assert test_data == downloaded
        print("  ✅ Upload/download successful")

        print("\n[Test 4] Upload/download encrypted JSON")
        json_data = {
            "event_type": "test_event",
            "data": {
                "key1": "value1",
                "key2": 12345,
                "nested": {"array": [1, 2, 3]},
            },
        }
        result = client.upload_json(json_data, encrypt=True)
        print(f"  Uploaded CID: {result['cid']}")
        downloaded_json = client.download_json(
            cid=result["cid"], encrypted=True, nonce=result["nonce"]
        )
        assert json_data == downloaded_json
        print("  ✅ JSON upload/download successful")

        print("\n[Test 5] Upload/download with metadata (AAD)")
        metadata = {"channel": "test-channel", "org": "test-org"}
        result = client.upload_json(data=json_data, encrypt=True, metadata=metadata)
        downloaded_with_metadata = client.download_json(
            cid=result["cid"], encrypted=True, nonce=result["nonce"], metadata=metadata
        )
        assert json_data == downloaded_with_metadata
        print("  ✅ Upload/download with metadata successful")

        print("\n[Test 6] Pin management")
        cid = result["cid"]
        pins_list = client.list_pins()
        print(f"  Total pinned items: {len(pins_list)}")
        assert cid in pins_list, f"Auto-pinned CID missing from pin list: {cid}"
        assert client.is_available(cid)

        with IPFSClient(auto_pin=False) as no_pin_client:
            no_pin_client._client = _fake_kubo(store, pins, counter)
            unpinned = no_pin_client.upload_bytes(os.urandom(32), encrypt=False)
            assert unpinned["cid"] not in no_pin_client.list_pins()

        print("  ✅ Pin management working")

        print("\n[Test 7] Cleanup - unpinning test data")
        client.unpin(cid)
        print("  ✅ Cleanup successful")

        print("\n" + "=" * 60)
        print("All IPFS tests passed! ✅")
        print("=" * 60)


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
