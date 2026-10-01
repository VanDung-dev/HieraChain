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

1. Durable writes: Writes records to Parquet files on disk before blocks finalize.
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
