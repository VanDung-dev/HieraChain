"""
Demo script for showcasing key backup and recovery functionality 
in the hierarchical blockchain framework.
"""

import os
import sys
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from security.key_backup_manager import KeyBackupManager, BackupError, RestoreError


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


def main():
    """Main demo function"""
    print("=== Hierarchical Blockchain Key Backup Demo ===\n")
    
    # Load configuration
    config = load_config()
    print("1. Loading key backup configuration...")
    print(f"   - Enabled: {config['enabled']}")
    print(f"   - Frequency: {config['frequency']}")
    print(f"   - Encryption: {config['encryption_algorithm']}")
    print(f"   - Locations: {config['locations']}")
    print(f"   - Integrity Check: {config['integrity_check']}")
    print(f"   - Retention Period: {config['retention_period']} days\n")
    
    # Initialize KeyBackupManager
    print("2. Initializing KeyBackupManager...")
    try:
        backup_manager = KeyBackupManager(config)
        print("   KeyBackupManager initialized successfully!\n")
    except Exception as e:
        print(f"   Error initializing KeyBackupManager: {e}")
        return
    
    # Generate sample keys
    print("3. Generating sample RSA key pair...")
    try:
        public_key, private_key = generate_sample_keys()
        print("   Sample key pair generated successfully!")
        print(f"   Public key size: {len(public_key)} bytes")
        print(f"   Private key size: {len(private_key)} bytes\n")
    except Exception as e:
        print(f"   Error generating keys: {e}")
        return
    
    # Backup keys
    print("4. Backing up keys...")
    try:
        backup_id = backup_manager.backup_keys(
            public_key=public_key,
            private_key=private_key,
            key_type="consensus"
        )
        print(f"   Keys backed up successfully with ID: {backup_id}\n")
    except BackupError as e:
        print(f"   Error during backup: {e}")
        return
    except Exception as e:
        print(f"   Unexpected error during backup: {e}")
        return
    
    # List backups
    print("5. Listing available backups...")
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
        return
    
    # Verify backup integrity
    print("6. Verifying backup integrity...")
    try:
        is_valid = backup_manager.verify_backup_integrity(backup_id)
        if is_valid:
            print("   Backup integrity verified successfully!\n")
        else:
            print("   Backup integrity check failed!\n")
            return
    except Exception as e:
        print(f"   Error verifying backup integrity: {e}")
        return
    
    # Restore keys
    print("7. Restoring keys from backup...")
    try:
        restored_keys = backup_manager.restore_keys(backup_id)
        print("   Keys restored successfully!")
        print(f"   Restored public key size: {len(restored_keys['public_key'])} bytes")
        print(f"   Restored private key size: {len(restored_keys['private_key'])} bytes\n")
        
        # Verify that restored keys match original keys
        if (restored_keys['public_key'] == public_key and 
            restored_keys['private_key'] == private_key):
            print("   Verification: Restored keys match original keys!\n")
        else:
            print("   Warning: Restored keys do not match original keys!\n")
            
    except RestoreError as e:
        print(f"   Error during restore: {e}")
        return
    except Exception as e:
        print(f"   Unexpected error during restore: {e}")
        return
    
    # Show backup locations
    print("8. Checking backup locations...")
    backup_locations_dir = os.path.join("backups")
    if os.path.exists(backup_locations_dir):
        for root, dirs, files in os.walk(backup_locations_dir):
            level = root.replace(backup_locations_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")
    else:
        print("   No backup locations found.")
    print()
    
    # Show metadata
    print("9. Backup metadata...")
    metadata_file = os.path.join("backups", "keys", "backup_metadata.json")
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            print("   Backup metadata loaded successfully:")
            print(f"   - Number of backups: {len(metadata)}")
            for backup_id, backup_info in metadata.items():
                print(f"   - Backup ID: {backup_id}")
                print(f"     Timestamp: {backup_info.get('timestamp', 'N/A')}")
                print(f"     Key type: {backup_info.get('key_type', 'N/A')}")
                print(f"     Locations: {backup_info.get('locations', [])}")
        except Exception as e:
            print(f"   Error reading metadata: {e}")
    else:
        print("   No metadata file found.")
    print()
    
    print("=== Demo completed successfully! ===")


if __name__ == "__main__":
    main()