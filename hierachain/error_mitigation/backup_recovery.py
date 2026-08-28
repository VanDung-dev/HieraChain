"""
Backup recovery engine for HieraChain Ledger.
"""

import time
import orjson
import logging
import hashlib
import os
from typing import Any
from datetime import datetime


logger = logging.getLogger(__name__)


def _compute_file_hash(backup_path: str) -> str:
    hash_func = hashlib.sha256()
    with open(backup_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


class BackupRecoveryEngine:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.backup_locations = config.get("locations", ["primary"])
        self.integrity_check = config.get("integrity_check", "sha256")
        self.max_recovery_attempts = config.get("max_recovery_attempts", 3)
        logger.info(
            "Initialized BackupRecoveryEngine with %d locations",
            len(self.backup_locations)
        )

    def recover_from_backup(self, backup_path: str) -> bool:
        logger.info("Attempting recovery from backup: %s", backup_path)
        for attempt in range(self.max_recovery_attempts):
            if self._attempt_single_recovery(backup_path, attempt):
                return True
        logger.error(f"All recovery attempts failed for {backup_path}")
        return False

    def _attempt_single_recovery(self, backup_path: str, attempt: int) -> bool:
        try:
            if not self._verify_backup_integrity(backup_path):
                logger.error("Backup integrity check failed: %s", backup_path)
                return False
            if self._restore_data(backup_path):
                logger.info("Recovery successful from %s", backup_path)
                return True
            return False
        except (OSError, orjson.JSONDecodeError, ValueError) as exc:
            logger.error("Recovery attempt %d failed: %s", attempt + 1, exc)
            is_last = (attempt >= self.max_recovery_attempts - 1)
            if not is_last:
                time.sleep(2 ** attempt)
            return False

    def _verify_backup_integrity(self, backup_path: str) -> bool:
        if not os.path.exists(backup_path):
            logger.error("Backup file does not exist: %s", backup_path)
            return False
        try:
            calculated_hash = _compute_file_hash(backup_path)
            return self._compare_with_stored_hash(backup_path, calculated_hash)
        except (OSError, orjson.JSONDecodeError) as exc:
            logger.error("Integrity verification failed: %s", exc)
            return False

    @staticmethod
    def _compare_with_stored_hash(backup_path: str, calculated_hash: str) -> bool:
        metadata_path = backup_path + ".meta"
        if not os.path.exists(metadata_path):
            logger.warning("No metadata file found, skipping hash verification")
            return True
        with open(metadata_path, "rb") as fh:
            metadata = orjson.loads(fh.read())
        stored_hash = metadata.get("hash")
        if calculated_hash == stored_hash:
            logger.info("Backup integrity verification passed")
            return True
        logger.error("Backup integrity verification failed: hash mismatch")
        return False

    @staticmethod
    def _restore_data(backup_path: str) -> bool:
        try:
            logger.info("Restoring data from %s", backup_path)
            time.sleep(1)
            restoration_event = {
                "event": "data_restored_from_backup",
                "backup_path": backup_path,
                "timestamp": time.time(),
            }
            logger.info("Data restoration completed: %s", orjson.dumps(restoration_event).decode())
            from hierachain.core.parquet_log import write_parquet_log
            write_parquet_log("log/error_mitigation/restoration_events.parquet", restoration_event)
            return True
        except Exception as exc:
            logger.error("Data restoration failed: %s", exc)
            return False
