"""
Unit tests for Ed25519 security utilities.
"""

from hierachain.security.security_utils import KeyPair, verify_signature


def test_keypair_generation():
    """Test that a key pair can be generated."""
    kp = KeyPair()
    assert kp.private_key is not None
    assert kp.public_key is not None
    assert len(kp.public_key) == 64  # Hex length of 32 bytes


def test_signing_verification():
    """Test signing and verifying a message."""
    kp = KeyPair()
    message = b"hello world"
    signature = kp.sign(message)

    assert len(signature) == 128  # Hex length of 64 bytes

    # Verify with helper
    assert verify_signature(kp.public_key, message, signature)

    # Verify failure with wrong message
    assert not verify_signature(kp.public_key, b"other message", signature)


def test_import_export():
    """Test exporting and importing a private key."""
    kp = KeyPair()
    priv_hex = kp.private_key

    kp2 = KeyPair.from_private_key(priv_hex)
    assert kp.public_key == kp2.public_key

    sig = kp.sign(b"test")
    sig2 = kp2.sign(b"test")
    assert sig == sig2
