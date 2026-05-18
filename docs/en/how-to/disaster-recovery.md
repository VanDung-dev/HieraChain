---
title: "Disaster Recovery"
description: "Details of TransactionJournal, RollbackManager, and KeyBackupManager mechanisms for handling interruptions and recovering the HieraChain system."
icon: material/backup-restore
---

# Disaster Recovery

HieraChain is designed with the highest priority on durability and system irreversibility. This document explains how the system automatically handles and how to operate recovery procedures when interruptions or server disasters occur.

---

## 1. Transaction Journaling (Replay Data)

To prevent data loss due to application crashes, power outages, or abrupt OS shutdown, HieraChain implements a **`TransactionJournal`** module before events are submitted to the Ordering Service for processing.

### How It Works

* **Storage Format:** Journal logs are serialized in **Apache Arrow RecordBatch** format, enabling extremely fast read/write speeds and preserving schema structure.
* **Length-Prefixed Framing:** Append-only files written in `[4-Byte Length][Batch Data]` structure.
* **Sync & Fsync:** All event log operations call `os.fsync()` to ensure disk I/O actually writes to hardware before returning success.

### Recovery Guide (Replay)

When a Node restarts after an unexpected crash, the system automatically checks the Log directory (default `data/journal/current.log`). The Node automatically iterates through the `replay()` method to replay RecordBatch sequences and fully restore the event array to memory (MemPool or World State).

---

## 2. Rollback State Management (`RollbackManager`)

In case of larger risks — such as data corruption or mistaken upgrades — the system allows rolling back the entire state to a safe checkpoint.

`RollbackManager` saves system state checkpoints:

* **Configuration State**: YAML, JSON, PY configuration files.
* **Chain State**: Block count and latest hash.
* **Consensus State**: View Number, current Leader Node ID.
* **Storage State**: World State Snapshot.

### Rollback Procedure

1. Get snapshot list via `manager.get_snapshots()`.
2. System checks **Integrity Hash** of the snapshot. Corrupted or too old (over 72 hours) snapshots will likely be rejected unless `force=True` is set.
3. Execute `rollback_to_snapshot(snapshot_id)`. It will restore each part of `Configuration` and `Chain State`.

---

## 3. Key Backup and Recovery (`KeyBackupManager`)

Protecting ECDSA/Ed25519 key pairs is critical. `KeyBackupManager` automatically creates secure backups when the system generates new Keys:

* **AES-256-GCM Security**: Node Public/Private Keys are collected, encrypted with GCM (Authenticated Encryption) using the Master Key provided by Admin.
* **Integrity Verification**: Uses `SHA-512` hashing combined with `HMAC` for verification each time recovery is performed.
* **Multi-location Distribution**: Hash and `.enc` files are distributed across multiple `locations` to prevent Single Point of Failure (SPOF).

### Recovery When Needed

Use `restore_keys(backup_id)`. The Manager will read the IO stream, verify `SHA-512` checksum, decrypt GCM, and immediately inject into the Node process without stopping the system. The key pair format is always verified by `_validate_keys` to prevent loading corrupted keys.

---

## 4. Network Error and Partition Handling (BFT Consensus Recovery)

HieraChain's BFT cluster (with View Change based algorithm) inherently contains "Self-recovery" properties for communication failures:

* **Leader Node-down Failure**: If the Leader crashes, times out (fails to broadcast new blocks on time), Validators send protest messages. When over `2f + 1` protest messages are reached, the system initiates a **View Change**, transferring to the next Leader (e.g., `Leader_ID = View_Number % Total_Nodes`).
* **Network Partition**: If the network splits into 2 partitions, the partition without the majority (***< 2f + 1***) automatically halts. The larger partition (over 66% of nodes) continues processing. When connection is restored, the smaller partition automatically calls P2P API to sync blocks with the longest chain.
