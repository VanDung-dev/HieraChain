"""
Encryption validator for HieraChain Ledger.

Validates encryption configurations and algorithms.
"""

from __future__ import annotations

import os
import json
import time
import logging
from typing import Any, cast

from hierachain.error_mitigation.validator_exceptions import SecurityError

logger = logging.getLogger(__name__)


class EncryptionValidator:
    def __init__(self, config: dict[str, Any]):
        self.config = config
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
            logger.warning("Key rotation interval %d below recommended %d", key_rotation_interval, self.min_key_rotation_interval)
            self._schedule_key_rotation()
        logger.info("Encryption configuration validation passed")
        return True

    def encrypt_data(self, data: str) -> dict[str, Any]:
        self.validate_config()
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            key = os.urandom(32)
            iv = os.urandom(12)
            encryptor = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend()).encryptor()
            ciphertext = encryptor.update(data.encode()) + encryptor.finalize()
            result = {
                "ciphertext": ciphertext,
                "tag": cast(Any, encryptor).tag,
                "iv": iv,
                "algorithm": "AES-256-GCM",
                "timestamp": time.time(),
            }
            logger.info("Data encrypted successfully")
            return result
        except Exception as ex:
            error_msg = f"Encryption failed: {str(ex)}"
            logger.error(error_msg)
            raise SecurityError(error_msg)

    def _schedule_key_rotation(self) -> None:
        rotation_event = {
            "event": "key_rotation_scheduled",
            "timestamp": time.time(),
            "next_rotation": time.time() + self.min_key_rotation_interval,
        }
        logger.info("Key rotation scheduled: %s", json.dumps(rotation_event))
