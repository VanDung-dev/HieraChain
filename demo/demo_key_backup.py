"""
Demo script for showcasing key backup and recovery functionality 
in the HieraChain Ledger.
"""

import os
import sys
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from hierachain.security import KeyBackupManager, BackupError, RestoreError

# Add parent directory to path to allow importing hierachain modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def generate_sample_keys():
    """Generate sample RSA key pair for demonstration"""
    # Generate a private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Get the public key
    public_key = private_key.public_key()
    
    # Serialize keys to bytes
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return public_bytes, private_bytes


def load_config():
    """Load key backup configuration from security profiles"""
    config = {
        "enabled": True,
        "frequency": "daily",
        "encryption_algorithm": "AES-256-GCM",
        "locations": ["primary_vault", "secondary_cloud"],
        "integrity_check": "sha512",
        "retention_period": 365,
        "auto_restore_threshold": 1
    }
    return config


def print_config(config):
    print("1. Loading key backup configuration...")
    print(f"   - Enabled: {config['enabled']}")
    print(f"   - Frequency: {config['frequency']}")
    print(f"   - Encryption: {config['encryption_algorithm']}")
    print(f"   - Locations: {config['locations']}")
    print(f"   - Integrity Check: {config['integrity_check']}")
    print(f"   - Retention Period: {config['retention_period']} days\n")


def init_backup_manager(config):
    print("2. Initializing KeyBackupManager...")
    try:
        backup_manager = KeyBackupManager(config)
        print("   KeyBackupManager initialized successfully!\n")
        return backup_manager
    except Exception as e:
        print(f"   Error initializing KeyBackupManager: {e}")
        return None


def generate_and_print_keys():
    print("3. Generating sample RSA key pair...")
    try:
        public_key, private_key = generate_sample_keys()
        print("   Sample key pair generated successfully!")
        print(f"   Public key size: {len(public_key)} bytes")
        print(f"   Private key size: {len(private_key)} bytes\n")
        return public_key, private_key
    except Exception as e:
        print(f"   Error generating keys: {e}")
        return None, None


def backup_keys_step(backup_manager, public_key, private_key):
    print("4. Backing up keys...")
    try:
        backup_id = backup_manager.backup_keys(
            public_key=public_key,
            private_key=private_key,
            key_type="consensus",
        )
        print(f"   Keys backed up successfully with ID: {backup_id}\n")
        return backup_id
    except BackupError as e:
        print(f"   Error during backup: {e}")
        return None
    except Exception as e:
        print(f"   Unexpected error during backup: {e}")
        return None


def list_backups_step(backup_manager):
    print("5. listing available backups...")
    try:
        backups = backup_manager.list_backups()
        print(f"   Found {len(backups)} backup(s):")
        for backup in backups:
            print(f"   - ID: {backup['backup_id']}")
            print(f"     Type: {backup['key_type']}")
            print(f"     Timestamp: {backup['timestamp']}")
            print(f"     Locations: {backup['locations']}\n")
    except Exception as e:
        print(f"   Error listing backups: {e}")
        return False
    return True


def verify_backup_step(backup_manager, backup_id):
    print("6. Verifying backup integrity...")
    try:
        is_valid = backup_manager.verify_backup_integrity(backup_id)
        if is_valid:
            print("   Backup integrity verified successfully!\n")
            return True
        print("   Backup integrity check failed!\n")
        return False
    except Exception as e:
        print(f"   Error verifying backup integrity: {e}")
        return False


def restore_keys_step(backup_manager, backup_id, public_key, private_key):
    print("7. Restoring keys from backup...")
    try:
        restored_keys = backup_manager.restore_keys(backup_id)
        print("   Keys restored successfully!")
        print(
            f"   Restored public key size: "
            f"{len(restored_keys['public_key'])} bytes"
        )
        print(
            f"   Restored private key size: "
            f"{len(restored_keys['private_key'])} bytes\n"
        )

        if (
            restored_keys["public_key"] == public_key
            and restored_keys["private_key"] == private_key
        ):
            print("   Verification: Restored keys match original keys!\n")
        else:
            print("   Warning: Restored keys do not match original keys!\n")
        return True
    except RestoreError as e:
        print(f"   Error during restore: {e}")
        return False
    except Exception as e:
        print(f"   Unexpected error during restore: {e}")
        return False


def show_backup_locations():
    print("8. Checking backup locations...")
    backup_locations_dir = "backups"
    if not os.path.exists(backup_locations_dir):
        backup_locations_dir = os.path.join("../backups")
        
    if os.path.exists(backup_locations_dir):
        for root, dirs, files in os.walk(backup_locations_dir):
            level = root.replace(backup_locations_dir, "").count(os.sep)
            indent = " " * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")
    else:
        print("   No backup locations found.")
    print()


def show_metadata():
    print("9. Backup metadata...")
    metadata_file = os.path.join("backups", "keys", "backup_metadata.json")
    if not os.path.exists(metadata_file):
        metadata_file = os.path.join("../backups", "keys", "backup_metadata.json")
        
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
            print("   Backup metadata loaded successfully:")
            print(f"   - Number of backups: {len(metadata)}")
            for backup_id, backup_info in metadata.items():
                print(f"   - Backup ID: {backup_id}")
                print(
                    f"     Timestamp: "
                    f"{backup_info.get('timestamp', 'N/A')}"
                )
                print(
                    f"     Key type: "
                    f"{backup_info.get('key_type', 'N/A')}"
                )
                print(
                    f"     Locations: "
                    f"{backup_info.get('locations', [])}"
                )
        except Exception as e:
            print(f"   Error reading metadata: {e}")
    else:
        print("   No metadata file found.")
    print()


def main():
    """Main demo function"""
    print("=== HieraChain Key Backup Demo ===\n")

    config = load_config()
    print_config(config)

    backup_manager = init_backup_manager(config)
    if backup_manager is None:
        return

    public_key, private_key = generate_and_print_keys()
    if public_key is None or private_key is None:
        return

    backup_id = backup_keys_step(backup_manager, public_key, private_key)
    if backup_id is None:
        return

    if not list_backups_step(backup_manager):
        return

    if not verify_backup_step(backup_manager, backup_id):
        return

    if not restore_keys_step(
        backup_manager, backup_id, public_key, private_key
    ):
        return

    show_backup_locations()
    show_metadata()

    print("=== Demo completed successfully! ===")


if __name__ == "__main__":
    main()
