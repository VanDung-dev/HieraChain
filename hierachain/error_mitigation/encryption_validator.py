"""
Encryption validator for HieraChain Ledger.

Validates encryption configurations and algorithms.
"""

from __future__ import annotations

import logging
import math
import os
import time
from collections.abc import Callable
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from hierachain.error_mitigation.validator_exceptions import SecurityError
from hierachain.serialization import dumps_canonical_json

logger = logging.getLogger(__name__)


class EncryptionValidator:
    def __init__(
        self, config: dict[str, Any], key_resolver: Callable[[str], bytes] | None = None,
    ) -> None:
        """Resolve retained AES keys by ID; key persistence belongs to the caller."""
        self.config = config
        self.key_resolver = key_resolver
        self.allowed_algorithms = ["AES-256-GCM"]
        self.min_key_rotation_interval = 2592000
        logger.info("Initialized EncryptionValidator")

    def validate_config(self) -> bool:
        algorithm = self.config.get("algorithm")
        if algorithm not in self.allowed_algorithms:
            error_msg = f"Weak encryption algorithm: {algorithm}. Only allowed: {', '.join(self.allowed_algorithms)}"
            logger.error(error_msg)
            raise SecurityError(error_msg)
        key_rotation_interval = self.config.get("key_rotation_interval", 0)
        if key_rotation_interval < self.min_key_rotation_interval:
            logger.warning(
                "Key rotation interval %d below recommended %d; rotation is managed by the host application",
                key_rotation_interval, self.min_key_rotation_interval,
            )
        logger.info("Encryption configuration validation passed")
        return True

    def encrypt_data(self, data: str) -> dict[str, Any]:
        """Encrypt UTF-8 text with the configured key ID and authenticated metadata."""
        self.validate_config()
        try:
            key_id = self.config.get("key_id")
            key = self._resolve_key(key_id)
            iv = os.urandom(12)
            result = {
                "algorithm": "AES-256-GCM",
                "key_id": key_id,
                "timestamp": time.time(),
            }
            encrypted = AESGCM(key).encrypt(iv, data.encode("utf-8"), self._associated_data(result))
            result.update({"ciphertext": encrypted[:-16], "tag": encrypted[-16:], "iv": iv})
            logger.info("Data encrypted successfully")
            return result
        except SecurityError:
            raise
        except Exception as exc:
            logger.error("Encryption failed")
            raise SecurityError("Encryption failed") from exc

    def decrypt_data(self, payload: dict[str, Any]) -> str:
        """Recover text using the envelope's retained key, including older key IDs."""
        self.validate_config()
        try:
            associated_data = self._associated_data(payload)
            key = self._resolve_key(payload["key_id"])
            ciphertext, tag, iv = payload["ciphertext"], payload["tag"], payload["iv"]
            if not all(isinstance(value, bytes) for value in (ciphertext, tag, iv)):
                raise SecurityError("Encrypted payload fields must be bytes")
            if len(tag) != 16 or len(iv) != 12:
                raise SecurityError("Invalid encryption tag or IV length")
            return AESGCM(key).decrypt(iv, ciphertext + tag, associated_data).decode("utf-8")
        except SecurityError:
            raise
        except Exception as exc:
            logger.error("Decryption failed")
            raise SecurityError("Decryption failed: invalid or tampered payload") from exc

    def _resolve_key(self, key_id: Any) -> bytes:
        """Require a caller-managed 256-bit key; never generate an unretained key."""
        if not isinstance(key_id, str) or not key_id.strip():
            raise SecurityError("A non-empty encryption key_id is required")
        if self.key_resolver is None:
            raise SecurityError("An encryption key_resolver is required")
        try:
            key = self.key_resolver(key_id)
        except Exception as exc:
            raise SecurityError("Encryption key unavailable") from exc
        if not isinstance(key, bytes) or len(key) != 32:
            raise SecurityError("Encryption key must be exactly 32 bytes")
        return key

    @staticmethod
    def _associated_data(payload: dict[str, Any]) -> bytes:
        """Bind the algorithm, key ID, and creation timestamp to the GCM tag."""
        if payload.get("algorithm") != "AES-256-GCM":
            raise SecurityError("Unsupported encrypted payload algorithm")
        timestamp = payload.get("timestamp")
        if (
            isinstance(timestamp, bool)
            or not isinstance(timestamp, (int, float))
            or not math.isfinite(timestamp)
            or timestamp <= 0
        ):
            raise SecurityError("Invalid encrypted payload timestamp")
        return dumps_canonical_json({field: payload[field] for field in ("algorithm", "key_id", "timestamp")})
