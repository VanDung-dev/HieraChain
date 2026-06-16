"""
Key Backup Manager for cryptographic key backup and recovery mechanisms.

This module handles backup and restoration of public and private keys to
enhance fault tolerance in the HieraChain Ledger without cryptocurrency
concepts.
"""

from __future__ import annotations

import os
import json
import shutil
import hashlib
import secrets
import base64
import binascii
from datetime import datetime, timedelta
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from hierachain.security.secure_logging import get_security_logger
from hierachain.security.master_key_provider import MasterKeyProvider
from hierachain.security.backup_types import (
    BackupError,
    RestoreError,
    IntegrityError,
    ValidationError,
)

logger = get_security_logger()

__all__ = [
    "BackupError",
    "RestoreError",
    "IntegrityError",
    "ValidationError",
    "KeyBackupManager",
    "create_key_backup_manager",
]


def _initialize_master_key(config: dict | None = None) -> bytes:
    provider = MasterKeyProvider(config)
    return provider.get_master_key()


def _load_existing_master_key(key_file: str) -> bytes:
    with open(key_file, "rb") as f:
        key = f.read()
    if len(key) == 44:
        try:
            decoded_key = base64.urlsafe_b64decode(key)
            if len(decoded_key) == 32:
                return decoded_key
        except (ValueError, binascii.Error):
            pass
    return key


def _generate_new_master_key(key_file: str) -> bytes:
    key = secrets.token_bytes(32)
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    with open(key_file, "wb") as f:
        f.write(key)
    try:
        os.chmod(key_file, 0o600)
    except OSError as e:
        logger.debug(f"Could not set file permissions on {key_file}: {e}")
    logger.info("Generated new master backup encryption key")
    return key


def _validate_keys(public_key: bytes, private_key: bytes, _key_type: str) -> bool:
    try:
        if not public_key or not private_key:
            return False
        if len(public_key) < 32 or len(private_key) < 32:
            return False
        return True
    except Exception as e:
        logger.error("Key validation failed: %s", str(e))
        return False


def _apply_restored_keys(public_key: bytes, private_key: bytes, key_type: str):
    logger.info(
        "Applied restored %s keys to system (public: %db, private: %db)",
        key_type, len(public_key), len(private_key)
    )


def _log_backup_success(backup_id: str, hash_value: str, locations: list[str]):
    log_entry = {
        "event_type": "key_backup_success",
        "backup_id": backup_id,
        "hash": hash_value,
        "locations": locations,
        "timestamp": datetime.now().isoformat(),
        "source": "KeyBackupManager"
    }
    logger.info("Key backup successful", extra=log_entry)


def _encrypt_backup_data(data: dict, encryption_key: bytes) -> bytes:
    aesgcm = AESGCM(encryption_key)
    nonce = secrets.token_bytes(12)
    json_data = json.dumps(data).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, json_data, None)
    return nonce + ciphertext


def _decrypt_backup_data(encrypted_data: bytes, encryption_key: bytes) -> dict:
    aesgcm = AESGCM(encryption_key)
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(decrypted_data.decode("utf-8"))


def _calculate_integrity_hash(data: bytes, algorithm: str) -> str:
    algorithms = {
        "sha512": hashlib.sha512,
        "sha256": hashlib.sha256,
    }
    hash_func = algorithms.get(algorithm, hashlib.sha512)
    return hash_func(data).hexdigest()


def _verify_integrity(file_path: str, expected_hash: str, algorithm: str) -> bool:
    try:
        with open(file_path, "rb") as f:
            actual_hash = _calculate_integrity_hash(f.read(), algorithm)
        return actual_hash == expected_hash
    except (IOError, OSError, ValueError):
        return False


def _distribute_to_locations(
    file_path: str, backup_id: str, locations: list[str], base_dir: str = "backups/keys"
) -> list[str]:
    distributed_locations: list[str] = []
    filename = f"{backup_id}.enc"
    for location in locations:
        try:
            location_path = os.path.join(base_dir, location)
            os.makedirs(location_path, exist_ok=True)
            dest_path = os.path.join(location_path, filename)
            shutil.copy2(file_path, dest_path)
            distributed_locations.append(location)
        except Exception as e:
            logger.error("Failed to distribute backup to %s: %s", location, str(e))
    return distributed_locations


def _cleanup_old_backups(metadata: dict, retention_period: int, remove_backup):
    cutoff_date = datetime.now() - timedelta(days=retention_period)
    backups_to_remove: list[str] = []
    for backup_id, entry in metadata.items():
        backup_time = datetime.fromisoformat(entry.get("timestamp", ""))
        if backup_time < cutoff_date:
            backups_to_remove.append(backup_id)
    for backup_id in backups_to_remove:
        try:
            remove_backup(backup_id)
            logger.info("Removed expired backup: %s", backup_id)
        except Exception as e:
            logger.error("Failed to remove expired backup %s: %s", backup_id, str(e))


def _find_backup_file(backup_id: str, metadata: dict, base_dir: str = "backups/keys") -> str | None:
    entry = metadata.get(backup_id)
    if not isinstance(entry, dict):
        return None
    primary_path: str | None = entry.get("file_path")
    if primary_path is not None:
        path_str = str(primary_path) if not isinstance(primary_path, str) else primary_path
        if os.path.exists(path_str):
            return path_str
    for location in entry.get("locations", []):
        file_path = os.path.join(base_dir, location, f"{backup_id}.enc")
        if os.path.exists(file_path):
            return file_path
    return None


def _get_backup_hash(backup_id: str, metadata: dict) -> str:
    entry = metadata.get(backup_id, {})
    return entry.get("hash", "")


def _load_metadata(metadata_file: str) -> dict:
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load backup metadata: %s", str(e))
            return {}
    return {}


def _save_metadata(metadata_file: str, metadata: dict):
    try:
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        logger.error("Failed to save backup metadata: %s", str(e))


def _update_metadata(metadata_file: str, metadata: dict, backup_id: str, entry: dict):
    metadata[backup_id] = entry
    _save_metadata(metadata_file, metadata)


class KeyBackupManager:
    def __init__(self, configuration: dict):
        self.config = configuration
        self.enabled = self.config.get('enabled', True)
        self.frequency = self.config.get('frequency', 'daily')
        self.encryption_algorithm = self.config.get(
            'encryption_algorithm', 'AES-256-GCM'
        )
        self.locations = self.config.get('locations', ['primary_vault'])
        self.integrity_check = self.config.get('integrity_check', 'sha512')
        self.retention_period = self.config.get('retention_period', 365)
        self.auto_restore_threshold = self.config.get('auto_restore_threshold', 1)

        master_key_config = self.config.get('master_key', None)
        self.encryption_key = _initialize_master_key(master_key_config)

        self.backup_dir = "backups/keys"
        os.makedirs(self.backup_dir, exist_ok=True)

        self.metadata_file = os.path.join(self.backup_dir, "backup_metadata.json")
        self.metadata = _load_metadata(self.metadata_file)

    def _calculate_integrity_hash(self, data: bytes) -> str:
        return _calculate_integrity_hash(data, self.integrity_check)

    def _verify_integrity(self, file_path: str, expected_hash: str) -> bool:
        return _verify_integrity(file_path, expected_hash, self.integrity_check)

    def _distribute_to_locations(self, file_path: str, backup_id: str) -> list[str]:
        return _distribute_to_locations(file_path, backup_id, self.locations, self.backup_dir)

    @staticmethod
    def _log_backup_success(backup_id: str, hash_value: str, locations: list[str]):
        _log_backup_success(backup_id, hash_value, locations)

    def backup_keys(
        self, public_key: bytes, private_key: bytes, key_type: str = "default"
    ) -> str:
        if not self.enabled:
            logger.info("Key backup is disabled, skipping backup")
            return ""
        try:
            timestamp = datetime.now().isoformat()
            sanitized_key_type = "".join(
                c for c in key_type if c.isalnum() or c in (' ', '-', '_')
            ).rstrip()
            sanitized_key_type = sanitized_key_type.replace(' ', '_')
            backup_id = f"{sanitized_key_type}_{timestamp.replace(':', '-')}"
            backup_data = {
                "public_key": public_key.hex(),
                "private_key": private_key.hex(),
                "key_type": key_type,
                "timestamp": timestamp,
                "algorithm": self.encryption_algorithm,
                "backup_id": backup_id
            }
            encrypted_data = _encrypt_backup_data(backup_data, self.encryption_key)
            backup_file = os.path.join(self.backup_dir, f"{backup_id}.enc")
            with open(backup_file, "wb", buffering=65536) as f:
                f.write(encrypted_data)
            hash_value = self._calculate_integrity_hash(encrypted_data)
            if not self._verify_integrity(backup_file, hash_value):
                raise BackupError("Backup integrity verification failed")
            distributed_locations = self._distribute_to_locations(
                backup_file, backup_id
            )
            self._update_metadata(backup_id, {
                "timestamp": timestamp,
                "key_type": key_type,
                "hash": hash_value,
                "locations": distributed_locations,
                "file_path": backup_file
            })
            self._cleanup_old_backups()
            self._log_backup_success(backup_id, hash_value, distributed_locations)
            logger.info(
                "Successfully backed up %s keys with ID: %s", key_type, backup_id
            )
            return backup_id
        except Exception as e:
            logger.error("Key backup failed: %s", str(e))
            raise BackupError(f"Failed to backup keys: {str(e)}")

    def restore_keys(self, backup_id: str) -> dict[str, bytes]:
        try:
            backup_file = self._find_backup_file(backup_id)
            if not backup_file:
                raise RestoreError(f"Backup file not found for ID: {backup_id}")
            with open(backup_file, "rb", buffering=65536) as f:
                encrypted_data = f.read()
            expected_hash = self._get_backup_hash(backup_id)
            actual_hash = self._calculate_integrity_hash(encrypted_data)
            if actual_hash != expected_hash:
                raise IntegrityError(f"Backup integrity check failed for {backup_id}")
            backup_data = _decrypt_backup_data(encrypted_data, self.encryption_key)
            public_key = bytes.fromhex(backup_data["public_key"])
            private_key = bytes.fromhex(backup_data["private_key"])
            if not _validate_keys(
                public_key, private_key, backup_data.get("key_type", "default")
            ):
                raise ValidationError("Restored keys failed validation")
            _apply_restored_keys(
                public_key, private_key, backup_data.get("key_type", "default")
            )
            logger.info("Successfully restored keys from backup: %s", backup_id)
            return {"public_key": public_key, "private_key": private_key}
        except Exception as e:
            logger.error("Key restore failed for %s: %s", backup_id, str(e))
            raise RestoreError(f"Failed to restore keys: {str(e)}")

    def list_backups(self, key_type: str | None = None) -> list[dict]:
        backups = []
        for backup_id, metadata in self.metadata.items():
            if key_type is None or metadata.get("key_type") == key_type:
                backups.append({
                    "backup_id": backup_id,
                    "timestamp": metadata.get("timestamp"),
                    "key_type": metadata.get("key_type"),
                    "locations": metadata.get("locations", [])
                })
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups

    def verify_backup_integrity(self, backup_id: str) -> bool:
        try:
            backup_file = self._find_backup_file(backup_id)
            if not backup_file:
                return False
            expected_hash = self._get_backup_hash(backup_id)
            return self._verify_integrity(backup_file, expected_hash)
        except Exception as e:
            logger.error(
                "Backup integrity verification failed for %s: %s", backup_id, str(e)
            )
            return False

    def _cleanup_old_backups(self):
        _cleanup_old_backups(self.metadata, self.retention_period, self._remove_backup)

    def _remove_backup(self, backup_id: str):
        metadata = self.metadata.get(backup_id, {})
        for location in metadata.get("locations", []):
            try:
                file_path = os.path.join(self.backup_dir, location, f"{backup_id}.enc")
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(
                    "Failed to remove backup file from %s: %s", location, str(e)
                )
        primary_file = metadata.get("file_path")
        if primary_file is not None:
            path_str = str(primary_file) if not isinstance(primary_file, str) else primary_file
            if os.path.exists(path_str):
                os.remove(path_str)
        del self.metadata[backup_id]
        self._save_metadata()

    def _find_backup_file(self, backup_id: str) -> str | None:
        return _find_backup_file(backup_id, self.metadata, self.backup_dir)

    def _get_backup_hash(self, backup_id: str) -> str:
        return _get_backup_hash(backup_id, self.metadata)

    def _load_metadata(self) -> dict:
        return _load_metadata(self.metadata_file)

    def _save_metadata(self):
        _save_metadata(self.metadata_file, self.metadata)

    def _update_metadata(self, backup_id: str, metadata: dict):
        _update_metadata(self.metadata_file, self.metadata, backup_id, metadata)


def create_key_backup_manager(configuration: dict) -> KeyBackupManager:
    return KeyBackupManager(configuration)
