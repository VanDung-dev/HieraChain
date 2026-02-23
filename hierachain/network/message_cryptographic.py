"""
P2P Message Cryptographic Protection for HieraChain.

This module provides cryptographic signing and verification for P2P messages,
ensuring message integrity, authenticity, and replay protection.

Features:
- Ed25519 digital signatures on all P2P messages
- Canonical payload serialization for deterministic signing
- Timestamp + nonce for replay attack prevention
- Message format: {payload, timestamp, nonce, sender_id, signature}
"""

import json
import time
import uuid
import logging
from typing import Any

from hierachain.security.security_utils import KeyPair, verify_signature

logger = logging.getLogger(__name__)


class MessageCryptoError(Exception):
    """Exception raised for message crypto errors."""
    pass


def create_signable_payload(
    payload: dict[str, Any],
    timestamp: float,
    nonce: str,
    sender_id: str,
) -> bytes:
    """
    Create canonical bytes representation of a message for signing.

    Uses sorted JSON serialization to ensure deterministic output
    regardless of dict key ordering.

    Args:
        payload: The message payload dict.
        timestamp: Unix timestamp of the message.
        nonce: Unique nonce for replay protection.
        sender_id: ID of the sending node.

    Returns:
        Canonical bytes for signing.
    """
    canonical = {
        "payload": payload,
        "timestamp": timestamp,
        "nonce": nonce,
        "sender_id": sender_id,
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_message(payload: dict[str, Any], keypair: KeyPair, sender_id: str) -> dict[str, Any]:
    """
    Create a signed P2P message.

    Args:
        payload: The message payload to sign.
        keypair: Ed25519 keypair for signing.
        sender_id: ID of the sending node.

    Returns:
        Signed message dict with payload, timestamp, nonce,
        sender_id, and signature fields.
    """
    ts = time.time()
    nonce = str(uuid.uuid4())

    signable = create_signable_payload(payload, ts, nonce, sender_id)
    signature = keypair.sign(signable)

    return {
        "payload": payload,
        "timestamp": ts,
        "nonce": nonce,
        "sender_id": sender_id,
        "signature": signature,
    }


def verify_message(message: dict[str, Any], public_key_hex: str) -> bool:
    """
    Verify the signature on a signed P2P message.

    Args:
        message: The signed message dict.
        public_key_hex: The sender's Ed25519 public key (hex).

    Returns:
        True if signature is valid, False otherwise.
    """
    try:
        payload = message.get("payload")
        ts = message.get("timestamp")
        nonce = message.get("nonce")
        sender_id = message.get("sender_id")
        signature = message.get("signature")

        if any(v is None for v in [payload, ts, nonce, sender_id, signature]):
            logger.warning("Message missing required fields for verification")
            return False

        signable = create_signable_payload(payload, ts, nonce, sender_id)
        return verify_signature(public_key_hex, signable, signature)

    except Exception as e:
        logger.error(f"Message verification failed: {e}")
        return False


def sign_handshake_payload(handshake_data: dict[str, Any], keypair: KeyPair) -> str:
    """
    Sign a handshake payload and return the signature.

    Args:
        handshake_data: The handshake payload (without signature field).
        keypair: Ed25519 keypair for signing.

    Returns:
        Hex-encoded signature string.
    """
    canonical = json.dumps(handshake_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return keypair.sign(canonical)


def verify_handshake_signature(
    handshake_data: dict[str, Any],
    signature: str,
    public_key_hex: str,
) -> bool:
    """
    Verify the signature on a handshake payload.

    Args:
        handshake_data: The handshake payload (without signature field).
        signature: Hex-encoded Ed25519 signature.
        public_key_hex: The sender's Ed25519 public key (hex).

    Returns:
        True if the signature is valid, False otherwise.
    """
    try:
        canonical = json.dumps(handshake_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return verify_signature(public_key_hex, canonical, signature)
    except Exception as e:
        logger.error(f"Handshake signature verification failed: {e}")
        return False
