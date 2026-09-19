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

* `Validator`: Validates block and event structure against ledger rules.
* `DataValidator`: Checks event payload consistency, Arrow schema alignment, and input constraints.

### 2.2 Durable journaling (`journal.py`)

* Implements `TransactionJournal` using Apache Parquet and Arrow for disk-backed event logging.
* Enforces append-only storage before events commit to blockchain state.
* Provides replay generators to reconstruct uncommitted events after ungraceful shutdowns.

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
