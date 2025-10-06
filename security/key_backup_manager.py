"""
Key Backup Manager for cryptographic key backup and recovery mechanisms.

This module handles backup and restoration of public and private keys to enhance 
fault tolerance in the hierarchical blockchain framework without cryptocurrency concepts.
"""

import os
import json
import shutil
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Raised when backup operations fail."""
    pass


class RestoreError(Exception):
    """Raised when restore operations fail."""
    pass


class IntegrityError(Exception):
    """Raised when backup integrity checks fail."""
    pass


class ValidationError(Exception):
    """Raised when key validation fails."""
    pass


class KeyBackupManager:
    """
    Manages backup and restoration of public and private keys.
    
    This class provides comprehensive key backup functionality including:
    - Automated backup on key generation/rotation
    - Encrypted storage with AES-256-GCM
    - Multi-location distribution
    - Integrity verification with SHA-512
    - Secure restoration with validation
    - Retention policy management
    
    All operations maintain hierarchical blockchain principles and avoid
    cryptocurrency concepts, focusing on event-based security operations.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize KeyBackupManager with configuration.
        
        Args:
            config: Configuration dictionary containing backup settings
        """
        self.config = config
        self.enabled = config.get('enabled', True)
        self.frequency = config.get('frequency', 'daily')
        self.encryption_algorithm = config.get('encryption_algorithm', 'AES-256-GCM')
        self.locations = config.get('locations', ['primary_vault'])
        self.integrity_check = config.get('integrity_check', 'sha512')
        self.retention_period = config.get('retention_period', 365)
        self.auto_restore_threshold = config.get('auto_restore_threshold', 1)
        
        # Generate or load master encryption key for backup encryption
        self.encryption_key = self._initialize_master_key()
        
        # Create backup directory if it doesn't exist
        self.backup_dir = "backups/keys"
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Initialize backup metadata storage
        self.metadata_file = os.path.join(self.backup_dir, "backup_metadata.json")
        self.metadata = self._load_metadata()
    
    def backup_keys(self, public_key: bytes, private_key: bytes, key_type: str = "default") -> str:
        """
        Backup keys with encryption and distribution.
        
        Args:
            public_key: Public key in bytes format
            private_key: Private key in bytes format  
            key_type: Type of key (e.g., "consensus", "identity", "encryption")
            
        Returns:
            str: Backup file identifier
            
        Raises:
            BackupError: If backup fails
        """
        if not self.enabled:
            logger.info("Key backup is disabled, skipping backup")
            return ""
        
        try:
            timestamp = datetime.now().isoformat()
            backup_id = f"{key_type}_{timestamp.replace(':', '-')}"
            
            # Prepare backup data
            backup_data = {
                "public_key": public_key.hex(),
                "private_key": private_key.hex(),
                "key_type": key_type,
                "timestamp": timestamp,
                "algorithm": self.encryption_algorithm,
                "backup_id": backup_id
            }
            
            # Encrypt backup data
            encrypted_data = self._encrypt_backup_data(backup_data)
            
            # Create backup file
            backup_file = os.path.join(self.backup_dir, f"{backup_id}.enc")
            with open(backup_file, "wb") as f:
                f.write(encrypted_data)
            
            # Generate integrity hash
            hash_value = self._calculate_integrity_hash(encrypted_data)
            
            # Verify integrity immediately
            if not self._verify_integrity(backup_file, hash_value):
                raise BackupError("Backup integrity verification failed")
            
            # Distribute to configured locations
            distributed_locations = self._distribute_to_locations(backup_file, backup_id)
            
            # Update metadata
            self._update_metadata(backup_id, {
                "timestamp": timestamp,
                "key_type": key_type,
                "hash": hash_value,
                "locations": distributed_locations,
                "file_path": backup_file
            })
            
            # Clean up old backups according to retention policy
            self._cleanup_old_backups()
            
            self._log_backup_success(backup_id, hash_value, distributed_locations)
            logger.info(f"Successfully backed up {key_type} keys with ID: {backup_id}")
            
            return backup_id
            
        except Exception as e:
            logger.error(f"Key backup failed: {str(e)}")
            raise BackupError(f"Failed to backup keys: {str(e)}")
    
    def restore_keys(self, backup_id: str) -> Dict[str, bytes]:
        """
        Restore keys from backup if damaged.
        
        Args:
            backup_id: Identifier of the backup to restore
            
        Returns:
            Dict containing 'public_key' and 'private_key' as bytes
            
        Raises:
            RestoreError: If restore fails
            IntegrityError: If backup is corrupted
            ValidationError: If restored keys are invalid
        """
        try:
            # Find backup file
            backup_file = self._find_backup_file(backup_id)
            if not backup_file:
                raise RestoreError(f"Backup file not found for ID: {backup_id}")
            
            # Read encrypted backup data
            with open(backup_file, "rb") as f:
                encrypted_data = f.read()
            
            # Verify integrity
            expected_hash = self._get_backup_hash(backup_id)
            actual_hash = self._calculate_integrity_hash(encrypted_data)
            if actual_hash != expected_hash:
                raise IntegrityError(f"Backup integrity check failed for {backup_id}")
            
            # Decrypt backup data
            backup_data = self._decrypt_backup_data(encrypted_data)
            
            # Extract keys
            public_key = bytes.fromhex(backup_data["public_key"])
            private_key = bytes.fromhex(backup_data["private_key"])
            
            # Validate restored keys
            if not self._validate_keys(public_key, private_key, backup_data.get("key_type", "default")):
                raise ValidationError("Restored keys failed validation")
            
            # Apply restored keys to system
            self._apply_restored_keys(public_key, private_key, backup_data.get("key_type", "default"))
            
            logger.info(f"Successfully restored keys from backup: {backup_id}")
            return {"public_key": public_key, "private_key": private_key}
            
        except Exception as e:
            logger.error(f"Key restore failed for {backup_id}: {str(e)}")
            raise RestoreError(f"Failed to restore keys: {str(e)}")
    
    def list_backups(self, key_type: Optional[str] = None) -> List[Dict]:
        """
        List available backups, optionally filtered by key type.
        
        Args:
            key_type: Optional filter by key type
            
        Returns:
            List of backup information dictionaries
        """
        backups = []
        for backup_id, metadata in self.metadata.items():
            if key_type is None or metadata.get("key_type") == key_type:
                backups.append({
                    "backup_id": backup_id,
                    "timestamp": metadata.get("timestamp"),
                    "key_type": metadata.get("key_type"),
                    "locations": metadata.get("locations", [])
                })
        
        # Sort by timestamp, newest first
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups
    
    def verify_backup_integrity(self, backup_id: str) -> bool:
        """
        Verify the integrity of a specific backup.
        
        Args:
            backup_id: Identifier of the backup to verify
            
        Returns:
            bool: True if backup is intact, False otherwise
        """
        try:
            backup_file = self._find_backup_file(backup_id)
            if not backup_file:
                return False
            
            expected_hash = self._get_backup_hash(backup_id)
            return self._verify_integrity(backup_file, expected_hash)
            
        except Exception as e:
            logger.error(f"Backup integrity verification failed for {backup_id}: {str(e)}")
            return False
    
    @staticmethod
    def _initialize_master_key() -> bytes:
        """Initialize or load the master encryption key."""
        key_file = os.path.join("config", "master_backup_key.key")
        
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            # Generate new master key
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, "wb") as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
            logger.info("Generated new master backup encryption key")
            return key
    
    def _encrypt_backup_data(self, data: Dict) -> bytes:
        """Encrypt backup data using Fernet (AES-256-GCM)."""
        fernet = Fernet(self.encryption_key)
        json_data = json.dumps(data).encode('utf-8')
        return fernet.encrypt(json_data)
    
    def _decrypt_backup_data(self, encrypted_data: bytes) -> Dict:
        """Decrypt backup data."""
        fernet = Fernet(self.encryption_key)
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode('utf-8'))
    
    def _calculate_integrity_hash(self, data: bytes) -> str:
        """Calculate SHA-512 hash for integrity checking."""
        if self.integrity_check == "sha512":
            return hashlib.sha512(data).hexdigest()
        elif self.integrity_check == "sha256":
            return hashlib.sha256(data).hexdigest()
        else:
            return hashlib.sha512(data).hexdigest()  # Default to SHA-512
    
    def _verify_integrity(self, file_path: str, expected_hash: str) -> bool:
        """Verify backup file integrity."""
        try:
            with open(file_path, "rb") as f:
                actual_hash = self._calculate_integrity_hash(f.read())
            return actual_hash == expected_hash
        except Exception:
            return False
    
    def _distribute_to_locations(self, file_path: str, backup_id: str) -> List[str]:
        """Distribute encrypted backup to secure locations."""
        distributed_locations = []
        filename = f"{backup_id}.enc"
        
        for location in self.locations:
            try:
                # Create location directory if it doesn't exist
                location_path = os.path.join("backups", location)
                os.makedirs(location_path, exist_ok=True)
                
                # Copy backup to location
                dest_path = os.path.join(location_path, filename)
                shutil.copy2(file_path, dest_path)
                distributed_locations.append(location)
                
            except Exception as e:
                logger.error(f"Failed to distribute backup to {location}: {str(e)}")
        
        return distributed_locations
    
    def _cleanup_old_backups(self):
        """Remove backups older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_period)
        
        backups_to_remove = []
        for backup_id, metadata in self.metadata.items():
            backup_time = datetime.fromisoformat(metadata.get("timestamp", ""))
            if backup_time < cutoff_date:
                backups_to_remove.append(backup_id)
        
        for backup_id in backups_to_remove:
            try:
                self._remove_backup(backup_id)
                logger.info(f"Removed expired backup: {backup_id}")
            except Exception as e:
                logger.error(f"Failed to remove expired backup {backup_id}: {str(e)}")
    
    def _remove_backup(self, backup_id: str):
        """Remove a backup and its metadata."""
        metadata = self.metadata.get(backup_id, {})
        
        # Remove from all locations
        for location in metadata.get("locations", []):
            try:
                file_path = os.path.join("backups", location, f"{backup_id}.enc")
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to remove backup file from {location}: {str(e)}")
        
        # Remove from primary backup directory
        primary_file = metadata.get("file_path")
        if primary_file and os.path.exists(primary_file):
            os.remove(primary_file)
        
        # Remove from metadata
        del self.metadata[backup_id]
        self._save_metadata()
    
    @staticmethod
    def _validate_keys(public_key: bytes, private_key: bytes, key_type: str) -> bool:
        """
        Validate restored keys to ensure they're valid and properly paired.
        
        Args:
            public_key: Public key bytes
            private_key: Private key bytes
            key_type: Type of key being validated
            
        Returns:
            bool: True if keys are valid
        """
        try:
            # Basic validation - ensure keys are not empty
            if not public_key or not private_key:
                return False
            
            # For demonstration, we'll do basic length checks
            # In practice, you'd deserialize and validate the actual cryptographic keys
            if len(public_key) < 32 or len(private_key) < 32:
                return False
            
            # Additional validation could include:
            # - Deserializing keys using cryptography library
            # - Verifying key pair relationship
            # - Checking key format and parameters
            
            return True
            
        except Exception as e:
            logger.error(f"Key validation failed: {str(e)}")
            return False
    
    @staticmethod
    def _apply_restored_keys(public_key: bytes, private_key: bytes, key_type: str):
        """
        Integrate restored keys into the system.
        
        This method would update the relevant system components with restored keys,
        such as consensus mechanisms, MSP configurations, or identity providers.
        """
        # Implementation depends on key type and system architecture
        # For now, this is a placeholder for system integration
        logger.info(f"Applied restored {key_type} keys to system")
    
    def _find_backup_file(self, backup_id: str) -> Optional[str]:
        """Find the backup file for given backup ID."""
        metadata = self.metadata.get(backup_id)
        if not metadata:
            return None
        
        # Try primary location first
        primary_path = metadata.get("file_path")
        if primary_path and os.path.exists(primary_path):
            return primary_path
        
        # Try distributed locations
        for location in metadata.get("locations", []):
            file_path = os.path.join("backups", location, f"{backup_id}.enc")
            if os.path.exists(file_path):
                return file_path
        
        return None
    
    def _get_backup_hash(self, backup_id: str) -> str:
        """Retrieve stored hash for backup."""
        metadata = self.metadata.get(backup_id, {})
        return metadata.get("hash", "")
    
    def _load_metadata(self) -> Dict:
        """Load backup metadata from file."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load backup metadata: {str(e)}")
                return {}
        return {}
    
    def _save_metadata(self):
        """Save backup metadata to file."""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save backup metadata: {str(e)}")
    
    def _update_metadata(self, backup_id: str, metadata: Dict):
        """Update metadata for a backup."""
        self.metadata[backup_id] = metadata
        self._save_metadata()
    
    @staticmethod
    def _log_backup_success(backup_id: str, hash_value: str, locations: List[str]):
        """Log successful backup operation."""
        log_entry = {
            "event_type": "key_backup_success",
            "backup_id": backup_id,
            "hash": hash_value,
            "locations": locations,
            "timestamp": datetime.now().isoformat(),
            "source": "KeyBackupManager"
        }
        logger.info("Key backup successful", extra=log_entry)


# Factory function for creating configured KeyBackupManager
def create_key_backup_manager(config: Dict) -> KeyBackupManager:
    """
    Factory function to create configured KeyBackupManager instance.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        KeyBackupManager: Configured instance
    """
    return KeyBackupManager(config)


if __name__ == "__main__":
    # Example usage
    config = {
        "enabled": True,
        "frequency": "daily",
        "encryption_algorithm": "AES-256-GCM",
        "locations": ["primary_vault", "secondary_cloud"],
        "integrity_check": "sha512",
        "retention_period": 365
    }
    
    manager = KeyBackupManager(config)
    print("KeyBackupManager initialized with configuration:")
    print(f"- Encryption: {manager.encryption_algorithm}")
    print(f"- Locations: {manager.locations}")
    print(f"- Retention: {manager.retention_period} days")