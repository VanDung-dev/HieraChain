"""
Security Utilities for HieraChain.

This module provides cryptographic primitives for the HieraChain framework,
focusing on Ed25519 for digital signatures as required for enterprise-grade security.
"""

from typing import Tuple, Optional, Any
import binascii
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder
from nacl.exceptions import BadSignatureError
import logging

logger = logging.getLogger(__name__)

class CryptoError(Exception):
    """Base exception for cryptographic errors."""
    pass

class KeyPair:
    """
    Represents an Ed25519 key pair for signing and verification.
    """
    def __init__(self, private_key: Optional[SigningKey] = None):
        if private_key:
            self._signing_key = private_key
        else:
            self._signing_key = SigningKey.generate()
        self._verify_key = self._signing_key.verify_key

    @property
    def public_key(self) -> str:
        """Return the public key as a hex string."""
        return self._verify_key.encode(encoder=HexEncoder).decode('utf-8')

    @property
    def private_key(self) -> str:
        """Return the private key as a hex string (CAUTION: Sensitive)."""
        return self._signing_key.encode(encoder=HexEncoder).decode('utf-8')

    @classmethod
    def generate(cls) -> 'KeyPair':
        """Generate a new random key pair."""
        return cls()

    @classmethod
    def from_private_key(cls, private_key_hex: str) -> 'KeyPair':
        """Load a key pair from a hex-encoded private key."""
        try:
            private_key_bytes = HexEncoder.decode(private_key_hex.encode('utf-8'))
            signing_key = SigningKey(private_key_bytes)
            return cls(signing_key)
        except Exception as e:
            raise CryptoError(f"Invalid private key format: {str(e)}")

    def sign(self, message: bytes) -> str:
        """
        Sign a message and return the signature as a hex string.
        
        Args:
            message: The message bytes to sign.
            
        Returns:
            Hex-encoded signature string.
        """
        try:
            signed = self._signing_key.sign(message)
            return signed.signature.hex()
        except Exception as e:
            raise CryptoError(f"Signing failed: {str(e)}")

def verify_signature_standalone(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """
    Pure function to verify an Ed25519 signature.
    Designed to be picklable for multiprocessing.

    Args:
        public_key_hex: The signer's public key in hex format.
        message: The original message bytes.
        signature_hex: The signature in hex format.

    Returns:
        True if valid, False otherwise.
    """
    try:
        # Decode public key and signature
        verify_key_bytes = HexEncoder.decode(public_key_hex.encode('utf-8'))
        verify_key = VerifyKey(verify_key_bytes)
        
        signature_bytes = binascii.unhexlify(signature_hex)
        
        # Verify
        verify_key.verify(message, signature_bytes)
        return True
    except (BadSignatureError, ValueError, binascii.Error):
        return False
    except Exception as e:
        # Logger might not work well in subprocess without config, but we try
        logger.error(f"Unexpected error during verification: {e}")
        return False

def verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """
    Verify an Ed25519 signature.
    
    Args:
        public_key_hex: The signer's public key in hex format.
        message: The original message bytes.
        signature_hex: The signature in hex format.

    Returns:
        True if valid, False otherwise.
    """
    return verify_signature_standalone(public_key_hex, message, signature_hex)

def generate_key_pair_hex() -> Tuple[str, str]:
    """
    Helper to generate a raw public/private key pair in hex.
    
    Returns:
        Tuple(public_key_hex, private_key_hex)
    """
    kp = KeyPair.generate()
    return kp.public_key, kp.private_key

def verify_batch_signatures(items: list[dict[str, Any]]) -> list[bool]:
    """
    Verify a batch of signatures, designed for multiprocessing.
    
    Args:
        items: List of dicts, each containing:
                - 'public_key': hex string
                - 'message': bytes or string (if string, will be encoded)
                - 'signature': hex string

    Returns:
        List of booleans corresponding to validity of each item.
    """
    results = []
    for item in items:
        try:
            pk = item.get('public_key')
            msg = item.get('message')
            sig = item.get('signature')
            
            if not pk or not msg or not sig:
                results.append(False)
                continue
                
            if isinstance(msg, str):
                msg = msg.encode('utf-8')
                
            results.append(verify_signature_standalone(pk, msg, sig))
        except Exception:
            results.append(False)
    return results
