"""
AES-256-GCM Encryption Module for IPFS Data.

This module provides encryption-at-rest for data stored in IPFS,
ensuring that even if CIDs are exposed, the underlying data remains secure.
Only authorized nodes with the correct encryption keys can decrypt the data.
"""

import os
import orjson
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from hierachain.security.secure_logging import SecureLogger

logger = SecureLogger("hierachain.storage.encryption")


class EncryptionError(Exception):
    """Base exception for encryption-related errors."""
    pass


class AESEncryption:
    """
    AES-256-GCM encryption handler for securing data before IPFS storage.

    Uses AES-256-GCM (Galois/Counter Mode) which provides:
    - Confidentiality: Data is encrypted
    - Authenticity: Built-in authentication tag prevents tampering
    - Performance: Hardware-accelerated on most modern CPUs

    Key Features:
    - 256-bit keys for maximum security
    - Unique nonce for each encryption operation
    - Authentication tag to detect tampering
    - Support for additional authenticated data (AAD)
    """

    def __init__(self, encryption_key: bytes | None = None):
        """
        Initialize AES encryption handler.

        Args:
            encryption_key: 32-byte encryption key. If None, generates a new key.
                            In production, this should come from secure key management.

        Raises:
            EncryptionError: If key is invalid
        """
        if encryption_key is None:
            self._key = AESGCM.generate_key(bit_length=256)
        else:
            self._key = encryption_key

        if len(self._key) != 32:
            raise EncryptionError("Encryption key must be exactly 32 bytes (256 bits)")

        self._aesgcm = AESGCM(self._key)

    @property
    def key(self) -> bytes:
        """Get the encryption key (handle with care - sensitive material)."""
        return self._key

    @classmethod
    def from_password(cls, password: str, salt: bytes | None = None) -> 'AESEncryption':
        """
        Derive an encryption key from a password using PBKDF2.

        Args:
            password: User password
            salt: Salt for key derivation. If None, generates random salt.
                  Store this salt to recreate the same key later.

        Returns:
            AESEncryption instance with derived key

        Note:
            This is useful for development/testing but in production,
            use proper key management systems (HSM, KMS, etc.)
        """
        effective_salt = salt if salt is not None else os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=effective_salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))

        return cls(encryption_key=key)

    def encrypt(
        self,
        plaintext: bytes,
        associated_data: bytes | None = None
    ) -> Tuple[bytes, bytes]:
        """
        Encrypt plaintext using AES-256-GCM.

        Args:
            plaintext: Data to encrypt
            associated_data: Optional additional authenticated data (AAD).
                           This data is authenticated but not encrypted.
                           Useful for metadata like CID, timestamp, etc.

        Returns:
            Tuple of (ciphertext, nonce)
            - ciphertext: Encrypted data with authentication tag appended
            - nonce: 12-byte nonce used for this encryption (must be stored)

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Generate a unique nonce for this encryption
            nonce = os.urandom(12)  # 96 bits recommended for GCM

            # Encrypt with optional AAD
            ciphertext = self._aesgcm.encrypt(nonce, plaintext, associated_data)

            logger.debug(
                "Data encrypted successfully",
                plaintext_size=len(plaintext),
                ciphertext_size=len(ciphertext)
            )

            return ciphertext, nonce

        except Exception as e:
            logger.error("Encryption failed", error=str(e))
            raise EncryptionError(f"Encryption failed: {str(e)}")

    def decrypt(
        self,
        ciphertext: bytes,
        nonce: bytes,
        associated_data: bytes | None = None
    ) -> bytes:
        """
        Decrypt ciphertext using AES-256-GCM.

        Args:
            ciphertext: Encrypted data with authentication tag
            nonce: 12-byte nonce used during encryption
            associated_data: Optional AAD (must match what was used in encryption)

        Returns:
            Decrypted plaintext

        Raises:
            EncryptionError: If decryption fails or data is tampered
        """
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, associated_data)

            logger.debug(
                "Data decrypted successfully",
                ciphertext_size=len(ciphertext),
                plaintext_size=len(plaintext)
            )

            return plaintext

        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise EncryptionError(f"Decryption failed (data may be tampered): {str(e)}")

    def encrypt_json(self, data: dict, associated_data: bytes | None = None) -> Tuple[bytes, bytes]:
        """
        Convenience method to encrypt JSON-serializable data.

        Args:
            data: Dictionary to encrypt
            associated_data: Optional AAD

        Returns:
            Tuple of (ciphertext, nonce)
        """
        try:
            plaintext = orjson.dumps(data, option=orjson.OPT_SORT_KEYS)
            return self.encrypt(plaintext, associated_data)
        except (TypeError, ValueError) as e:
            raise EncryptionError(f"JSON serialization failed: {str(e)}")

    def decrypt_json(
        self,
        ciphertext: bytes,
        nonce: bytes,
        associated_data: bytes | None = None
    ) -> dict:
        """
        Convenience method to decrypt JSON data.

        Args:
            ciphertext: Encrypted JSON data
            nonce: Nonce used during encryption
            associated_data: Optional AAD

        Returns:
            Decrypted dictionary
        """
        plaintext = self.decrypt(ciphertext, nonce, associated_data)
        try:
            return orjson.loads(plaintext)
        except (orjson.JSONDecodeError, UnicodeDecodeError) as e:
            raise EncryptionError(f"JSON deserialization failed: {str(e)}")

    @staticmethod
    def generate_key() -> bytes:
        """
        Generate a new random 256-bit encryption key.

        Returns:
            32-byte encryption key
        """
        return AESGCM.generate_key(bit_length=256)

    def __repr__(self) -> str:
        return f"<AESEncryption key_length=256bits>"
