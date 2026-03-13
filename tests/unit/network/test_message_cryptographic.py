"""
Tests for P2P message cryptographic protection.

Covers:
- Sign and verify message roundtrip
- Reject tampered message (modified payload)
- Reject message with spoofed sender (signed with wrong key)
- Reject message with missing fields
- Verify canonical payload determinism
"""

import time
import pytest

from hierachain.network import (
    sign_message,
    verify_message,
    create_signable_payload,
    sign_handshake_payload,
    verify_handshake_signature,
)
from hierachain.security import KeyPair


class TestMessageSignVerify:
    """Test P2P message signing and verification."""

    @pytest.fixture
    def keypair(self):
        return KeyPair.generate()

    @pytest.fixture
    def other_keypair(self):
        return KeyPair.generate()

    def test_sign_verify_roundtrip(self, keypair):
        """Signed message should verify successfully."""
        payload = {"action": "sync_block", "block_id": 42}
        message = sign_message(payload, keypair, "node-1")

        assert verify_message(message, keypair.public_key) is True

    def test_message_structure(self, keypair):
        """Signed message should contain all required fields."""
        payload = {"data": "test"}
        message = sign_message(payload, keypair, "node-1")

        assert "payload" in message
        assert "timestamp" in message
        assert "nonce" in message
        assert "sender_id" in message
        assert "signature" in message
        assert message["payload"] == payload
        assert message["sender_id"] == "node-1"

    def test_tampered_payload_rejected(self, keypair):
        """Message with tampered payload should fail verification."""
        payload = {"amount": 100}
        message = sign_message(payload, keypair, "node-1")

        # Tamper with the payload
        message["payload"]["amount"] = 999999

        assert verify_message(message, keypair.public_key) is False

    def test_tampered_timestamp_rejected(self, keypair):
        """Message with altered timestamp should fail verification."""
        payload = {"data": "test"}
        message = sign_message(payload, keypair, "node-1")

        # Alter timestamp
        message["timestamp"] = time.time() + 1000

        assert verify_message(message, keypair.public_key) is False

    def test_tampered_nonce_rejected(self, keypair):
        """Message with altered nonce should fail verification."""
        payload = {"data": "test"}
        message = sign_message(payload, keypair, "node-1")

        # Alter nonce
        message["nonce"] = "forged-nonce"

        assert verify_message(message, keypair.public_key) is False

    def test_spoofed_sender_rejected(self, keypair, other_keypair):
        """Message signed by wrong key should fail verification."""
        payload = {"data": "test"}
        # Sign with other_keypair but verify with keypair
        message = sign_message(payload, other_keypair, "node-attacker")

        assert verify_message(message, keypair.public_key) is False

    def test_missing_signature_rejected(self, keypair):
        """Message without signature should fail verification."""
        message = {
            "payload": {"data": "test"},
            "timestamp": time.time(),
            "nonce": "some-nonce",
            "sender_id": "node-1",
        }

        assert verify_message(message, keypair.public_key) is False

    def test_missing_timestamp_rejected(self, keypair):
        """Message without timestamp should fail verification."""
        message = {
            "payload": {"data": "test"},
            "nonce": "some-nonce",
            "sender_id": "node-1",
            "signature": "some-sig",
        }

        assert verify_message(message, keypair.public_key) is False

    def test_missing_nonce_rejected(self, keypair):
        """Message without nonce should fail verification."""
        message = {
            "payload": {"data": "test"},
            "timestamp": time.time(),
            "sender_id": "node-1",
            "signature": "some-sig",
        }

        assert verify_message(message, keypair.public_key) is False

    def test_unique_nonces(self, keypair):
        """Each signed message should have a unique nonce."""
        payload = {"data": "test"}
        msg1 = sign_message(payload, keypair, "node-1")
        msg2 = sign_message(payload, keypair, "node-1")

        assert msg1["nonce"] != msg2["nonce"]

    def test_unique_signatures(self, keypair):
        """Same payload should produce different signatures (due to nonce)."""
        payload = {"data": "test"}
        msg1 = sign_message(payload, keypair, "node-1")
        msg2 = sign_message(payload, keypair, "node-1")

        assert msg1["signature"] != msg2["signature"]


class TestCanonicalPayload:
    """Test deterministic canonical serialization."""

    def test_deterministic_ordering(self):
        """Same logical payload should produce same canonical bytes."""
        payload1 = {"b": 2, "a": 1}
        payload2 = {"a": 1, "b": 2}

        bytes1 = create_signable_payload(payload1, 1000.0, "nonce", "node")
        bytes2 = create_signable_payload(payload2, 1000.0, "nonce", "node")

        assert bytes1 == bytes2

    def test_different_payloads_differ(self):
        """Different payloads should produce different canonical bytes."""
        bytes1 = create_signable_payload(
            {"a": 1}, 1000.0, "nonce", "node"
        )
        bytes2 = create_signable_payload(
            {"a": 2}, 1000.0, "nonce", "node"
        )

        assert bytes1 != bytes2

    def test_different_timestamps_differ(self):
        """Different timestamps should produce different bytes."""
        payload = {"a": 1}
        bytes1 = create_signable_payload(payload, 1000.0, "nonce", "node")
        bytes2 = create_signable_payload(payload, 2000.0, "nonce", "node")

        assert bytes1 != bytes2


class TestHandshakePayloadCrypto:
    """Test handshake-specific signing and verification."""

    @pytest.fixture
    def keypair(self):
        return KeyPair.generate()

    def test_sign_verify_handshake(self, keypair):
        """Handshake payload should sign and verify correctly."""
        data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-1",
        }
        sig = sign_handshake_payload(data, keypair)
        assert verify_handshake_signature(
            data, sig, keypair.public_key
        ) is True

    def test_tampered_handshake_rejected(self, keypair):
        """Tampered handshake payload should fail verification."""
        data = {
            "type": "HANDSHAKE_INIT",
            "sender_msp_id": "org-1",
            "certificate_id": "node-1",
        }
        sig = sign_handshake_payload(data, keypair)
        data["certificate_id"] = "node-evil"
        assert verify_handshake_signature(
            data, sig, keypair.public_key
        ) is False

    def test_wrong_key_handshake_rejected(self, keypair):
        """Handshake verified with wrong key should fail."""
        other = KeyPair.generate()
        data = {"type": "HANDSHAKE_INIT"}
        sig = sign_handshake_payload(data, keypair)
        assert verify_handshake_signature(
            data, sig, other.public_key
        ) is False
