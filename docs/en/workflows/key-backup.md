---
title: "Key Backup & Restoration"
description: "Cryptographic backup of critical validator private keys and system restoration procedures."
icon: material/key
---

# Key Backup & Restoration

## Overview

Cryptographic keys (consensus keys, identity keys, encryption keys) are backed up automatically after each generation or rotation event. Each backup is **AES-256-GCM encrypted** and distributed to multiple vault locations. When restoring, `restore_keys()` verifies **SHA-512 integrity** before decrypting and applying keys to the system.

**Key property**: Even if one vault is compromised, the plaintext keys are protected by AES-256-GCM. Even if the ciphertext is tampered, the SHA-512 integrity check prevents decryption of corrupted data.

---

## Flow Diagram — Backup

```mermaid
sequenceDiagram
    autonumber
    participant Trigger as ⚙️ Key Generation / Rotation
    participant KBM as 🔑 KeyBackupManager
    participant AES as 🔐 AES-256-GCM
    participant FS as 📁 File System / Vault

    Note over Trigger: New key created (MSP cert issue, consensus rotation)

    Trigger->>KBM: backup_keys(public_key, private_key, key_type)
    KBM->>KBM: Sanitize key_type → backup_id = "{key_type}_{timestamp}"

    rect rgb(0, 0, 0, 0)
        Note over KBM,AES: Phase 1 — Encryption
        KBM->>AES: _encrypt_backup_data({ public_key, private_key, ... }, encryption_key)
        Note right of AES: nonce = secrets.token_bytes(12)<br/>ciphertext = AESGCM.encrypt(nonce, json_data, aad)<br/>output = nonce || ciphertext
        AES-->>KBM: encrypted_data (bytes)
    end

    rect rgb(0, 0, 0, 0)
        Note over KBM,FS: Phase 2 — Write & Integrity Verify
        KBM->>FS: write {backup_id}.enc to primary vault
        KBM->>KBM: _calculate_integrity_hash(encrypted_data) → SHA-512
        KBM->>KBM: _verify_integrity(backup_file, expected_hash) → confirm write OK
    end

    rect rgb(0, 0, 0, 0)
        Note over KBM,FS: Phase 3 — Distribution & Metadata
        KBM->>FS: _distribute_to_locations(file, backup_id, locations)
        Note right of FS: Copy to secondary_vault, tertiary_vault, ...<br/>Each = separate directory / remote path
        FS-->>KBM: distributed_locations []

        KBM->>KBM: _update_metadata(backup_id, { timestamp, key_type, hash, locations, file_path })
        KBM->>KBM: _cleanup_old_backups() — remove backups older than retention_period days
    end
    KBM-->>Trigger: backup_id ✅
```

---

## Flow Diagram — Restoration

```mermaid
sequenceDiagram
    autonumber
    participant Trigger as ⚙️ Disaster Recovery
    participant KBM as 🔑 KeyBackupManager
    participant AES as 🔐 AES-256-GCM
    participant FS as 📁 File System / Vault

    Trigger->>KBM: restore_keys(backup_id)
    rect rgb(0, 0, 0, 0)
        Note over KBM,FS: Phase 1 — Locate & Integrity Check
        KBM->>FS: _find_backup_file(backup_id)<br/>Search primary vault, then distributed locations
        FS-->>KBM: backup_file path

        KBM->>KBM: _get_backup_hash(backup_id) → expected_hash from metadata
        KBM->>KBM: _calculate_integrity_hash(file_content) → actual_hash
    end

    alt Integrity OK (actual == expected)
        KBM->>AES: _decrypt_backup_data(encrypted_data, encryption_key)
        AES-->>KBM: { public_key, private_key, key_type }
        KBM->>KBM: _validate_keys(public_key, private_key, key_type)
        KBM->>KBM: _apply_restored_keys(public_key, private_key, key_type)
        KBM-->>Trigger: { public_key, private_key } ✅
    else Integrity FAIL (tampered or corrupted)
        KBM-->>Trigger: raise IntegrityError ❌
        Note over KBM: Log corruption, try next vault location
    end
```

---

## Multi-Vault Failover

```mermaid
flowchart LR
    RESTORE["restore_keys(backup_id)"]
    ledger["📁 Primary Vault\n_find_backup_file()"]
    business["📁 Secondary Vault\n(fallback)"]
    admin["📁 Tertiary Vault\n(fallback)"]
    OK["✅ Decrypted Keys"]
    ERR["❌ IntegrityError\nAll vaults failed"]

    RESTORE --> ledger
    ledger -->|Found + intact| OK
    ledger -->|Not found / tampered| business
    business -->|Found + intact| OK
    business -->|Not found / tampered| admin
    admin -->|Found + intact| OK
    admin -->|Not found / tampered| ERR
```

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Trigger** | Key generated (MSP cert issue) or rotated (scheduled rotation) |
| **2. Backup ID** | `backup_id = "{sanitized_key_type}_{unix_timestamp}"` |
| **3. Encrypt** | AES-256-GCM with random 96-bit nonce. Output = `nonce \|\| ciphertext` |
| **4. Write + verify** | Write to primary vault; SHA-512 hash of file verified immediately |
| **5. Distribute** | Copy to all configured vault locations |
| **6. Metadata** | `metadata.json` updated: backup_id, key_type, hash, locations, timestamp |
| **7. Cleanup** | Backups older than `retention_period` (default 365 days) deleted |
| **8. Restore** | Find file → verify SHA-512 → decrypt → validate key pair → apply |

---

## Backup Configuration

| Parameter | Default | Description |
|:----------|:--------|:------------|
| `frequency` | `daily` | Backup schedule |
| `encryption_algorithm` | `AES-256-GCM` | Cipher |
| `integrity_check` | `sha512` | Hash algorithm for write verification |
| `retention_period` | `365` days | Auto-cleanup threshold |
| `locations` | `[primary_vault]` | Distribution targets |
| `auto_restore_threshold` | `1` | Min available copies before auto-restore triggered |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| Integrity check fails immediately after write | `ValueError` raised; backup aborted, retried |
| All vault locations unreachable | `IOError` raised; critical alert via Risk Alerts |
| SHA-512 mismatch on restore | `IntegrityError` raised; next vault location tried |
| Decryption fails (wrong key) | `CryptographyError` raised; process aborted |
| `_apply_restored_keys()` fails | System remains on existing keys; error logged and alerted |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Backup entry | `KeyBackupManager.backup_keys()` | `security/key_backup_manager.py` |
| Encrypt | `_encrypt_backup_data()` | `security/key_backup_manager.py` |
| Integrity hash | `_calculate_integrity_hash()` | `security/key_backup_manager.py` |
| Verify write | `_verify_integrity()` | `security/key_backup_manager.py` |
| Distribute | `_distribute_to_locations()` | `security/key_backup_manager.py` |
| Restore entry | `KeyBackupManager.restore_keys()` | `security/key_backup_manager.py` |
| Find file | `_find_backup_file()` | `security/key_backup_manager.py` |
| Decrypt | `_decrypt_backup_data()` | `security/key_backup_manager.py` |
| Validate keys | `_validate_keys()` | `security/key_backup_manager.py` |
| Master key | `MasterKeyProvider.get_master_key()` | `security/master_key_provider.py` |

---

## Related

- [MSP Identity](./msp-identity.md) — certificate issuance triggers key backup
- [Cluster Lockdown](./cluster-lockdown.md) — lockdown may require key rotation, triggering this workflow
- [IPFS Storage](./ipfs-storage.md) — uses the same AES-256-GCM encryption pattern
