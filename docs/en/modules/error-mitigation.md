---
title: "Error Mitigation Module"
description: "Runtime validation, durable journaling, and error classification."
icon: material/bug
---

# Error Mitigation Module (`hierachain/error_mitigation/*`)

## 1. Overview

The `error_mitigation` module provides the runtime primitives for state validation, durable journaling, and error classification. Consensus view changes and operational restoration remain owned by their respective runtime or deployment layers.

## 2. Core components

Components reside in `hierachain/error_mitigation/`.

### 2.1 Validation layer (`validator.py`, `data_validator.py`)

* `validate_certificate()`: Rejects expired certificates.
* `DataValidator`: Checks event payload consistency, Arrow schema alignment, and input constraints.

Custom field validators return `(is_valid, message)`. If a callback raises an exception or returns an invalid result, `DataValidator` records an error and returns `ValidationResult.is_valid=False`, including in batch validation. Validation level and automatic fixes do not override this failure.

### 2.2 Durable journaling (`journal.py`)

* Implements `TransactionJournal` using Apache Parquet and Arrow for disk-backed event logging.
* Enforces append-only storage before events commit to blockchain state.
* Provides replay generators to reconstruct uncommitted events after ungraceful shutdowns.

`read_since(cursor=None)` flushes and fsyncs the active writer, reads durable frames, and returns `(records, (inode, byte_offset))`. The first call scans history, including legacy Parquet; later calls read new Arrow frames and follow file rotation. A missing active file, missing or truncated cursor file, corrupt frame, or fsync error rejects read-back. Archive filenames are still enumerated on each call, so cost depends on archive count as well as new records.

Each append records its starting offset. If writing or fsyncing a frame fails, the journal truncates to that offset and fsyncs the truncation before allowing another append. If truncation or its fsync fails, the writer is poisoned and rejects writes until it is closed and reopened as a new instance; startup repairs an incomplete active tail.

### 2.3 Recoverable encryption (`encryption_validator.py`)

`EncryptionValidator(config, key_resolver)` uses AES-256-GCM. Encryption requires `config["key_id"]` and a caller-supplied `key_resolver(key_id)` that returns exactly 32 bytes for an approved, retained key. Missing IDs, unavailable keys, or invalid key material raise `SecurityError`; the validator does not generate disposable encryption keys.

`encrypt_data(text)` returns `ciphertext`, `tag`, and `iv` as bytes, plus `algorithm`, `key_id`, and `timestamp`. The GCM tag authenticates the ciphertext, algorithm, key ID, and timestamp. `decrypt_data(envelope)` resolves the key ID in the envelope, so older data remains readable after the configured encryption key ID changes, provided its original key is retained. Missing or tampered envelope fields raise `SecurityError`.

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from hierachain.error_mitigation import EncryptionValidator

keys = {"data-v1": AESGCM.generate_key(bit_length=256)}
validator = EncryptionValidator(
    {"algorithm": "AES-256-GCM", "key_id": "data-v1"},
    key_resolver=keys.__getitem__,
)
envelope = validator.encrypt_data("business event")
reader = EncryptionValidator({"algorithm": "AES-256-GCM"}, key_resolver=keys.__getitem__)
assert reader.decrypt_data(envelope) == "business event"
```

This example retains keys in memory. Production callers must preserve keys in their existing secure key store and restore the resolver after restart; keys are never embedded in the envelope. Encode the byte fields as Base64 for JSON storage and decode them back to bytes before decryption. The module's rotation notification does not provision or retain keys automatically. Older ciphertext whose random key was discarded by the previous implementation cannot be recovered by this change.

### 2.4 Capacity and key rotation advice

`ConsensusValidator.validate_node_count()` still rejects fewer than `3f+1` nodes. The legacy `monitor_and_scale()` method only returns healthy nodes and logs a capacity recommendation when their ratio falls below `auto_scale_threshold`; it neither changes membership nor restores quorum. The BFT runtime calls the node-count validator, but does not automatically invoke this health monitor.

`ResourceValidator.validate_resources()` reports CPU, memory, and disk threshold violations. The legacy `auto_scale=True` flag additionally writes CPU/memory capacity recommendations; disk violations only produce warnings. Callers must invoke these checks themselves and handle provisioning through their host infrastructure.

`EncryptionValidator.validate_config()` warns when `key_rotation_interval` is below the existing `min_key_rotation_interval` (2,592,000 seconds). This is an advisory configuration comparison, not an evaluation of key age or an expiry policy. It creates no schedule, deadline, or replacement key. The host application manages rotation and retention of old keys.

Log consumers must update their event filters: `auto_scaling_triggered` and its `consensus_scaling` wrapper become `consensus_capacity_recommendation`; `resource_scaling_triggered` becomes `resource_capacity_recommendation`. The legacy Parquet paths `log/error_mitigation/consensus_scaling.parquet` and `log/error_mitigation/resource_scaling.parquet`, payload fields (including `auto_scale_enabled`), and existing records remain compatible. The misleading `key_rotation_scheduled` log and `next_rotation` field are removed; the interval warning remains.

## 3. Error classification strategy

`ErrorClassifier` in `error_classifier.py` categorizes errors by severity and recommends mitigation actions:

| Severity Level | Category Meaning | Mitigation Action |
| :--- | :--- | :--- |
| INFO / WARNING | Minor operational anomalies | Log and continue |
| ERROR | Event validation or transient processing failures | Retry with backoff or reject |
| CRITICAL | State corruption or Merkle root mismatch | Reject, log, and require operational recovery |
| FATAL | Irrecoverable consensus or hardware failure | Emergency lockdown |

## 4. Transaction journaling

The `TransactionJournal` provides write-ahead persistence:

1. Durable writes: Appends framed Arrow records and fsyncs them on disk before blocks finalize; legacy Parquet remains readable.
2. Schema enforcement: Guarantees every journal record matches the required event schema.
3. Replay ability: Replays logged events from disk into the ordering pipeline during node restart.

```python
from hierachain.error_mitigation.journal import TransactionJournal

journal = TransactionJournal(storage_dir="data/journal")
journal.log_event(event_dict)
```

## Related

* [Adapters Module](./adapters.md)
* [Core Module](./core.md)
* [Cluster Lockdown](./cluster.md)

`ErrorClassifier` invokes a supplied lockdown callback for HIGH or CRITICAL security classifications and CRITICAL performance classifications. `DataValidator.validate_table()` checks required Arrow types at all levels; strict validation additionally rejects nulls. Consistency checks compare rows in order, including decoded JSON details. Journal directory walks and file opens reject symlinks using directory descriptors and no-follow flags.

The journal fsyncs directory entries after creation and rotation. New journal frames preserve typed `details` and original field presence in the binary envelope, so domain registration and stable-ID retries survive replay. The updated reader accepts older envelopes and legacy Parquet archives; older readers do not understand the extended envelope, so upgrade the reader before writing the new format. Metadata omitted from historical registration events cannot be reconstructed. Each journal path requires one owning process; see [local journal ownership](../consensus/ordering.md#local-journal-ownership).
