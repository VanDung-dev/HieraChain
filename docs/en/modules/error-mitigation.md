---
title: "Error Mitigation Module"
description: "Durable transaction journaling for the hierarchical ledger."
icon: material/bug
---

# Error Mitigation Module (`hierachain/error_mitigation/*`)

## 1. Overview

The `error_mitigation` module provides durable transaction journaling. Operational restoration remains owned by the deployment layer.

## 2. Transaction journaling (`journal.py`)

`TransactionJournal` provides write-ahead persistence:

1. Durable writes: Appends framed Arrow records and fsyncs them on disk before blocks finalize; legacy Parquet remains readable.
2. Schema enforcement: Guarantees every journal record matches the required event schema.
3. Replay ability: Replays logged events from disk into the ordering pipeline during node restart.

```python
from hierachain.error_mitigation.journal import TransactionJournal

journal = TransactionJournal(storage_dir="data/journal")
journal.log_event(event_dict)
```

`read_since(cursor=None)` flushes the active writer and fsyncs it only when its file state is unknown or has changed. Successful appends are already fsynced before `log_event()` returns. It reads durable frames and returns `(records, (inode, byte_offset))`. The first call scans history, including legacy Parquet; later calls read new Arrow frames and follow file rotation. A missing active file, missing or truncated cursor file, corrupt frame, or required fsync error rejects read-back. Archive filenames are still enumerated on each call, so cost depends on archive count as well as new records.

Each append records its starting offset. If writing or fsyncing a frame fails, the journal truncates to that offset and fsyncs the truncation before allowing another append. If truncation or its fsync fails, the writer is poisoned and rejects writes until it is reopened through `_open_journal()` or the journal is cleared. Reopening the same instance resets the poison flag; startup also repairs an incomplete active tail. Replay enumerates legacy archives before timestamped rotated files and orders the rotated files numerically by timestamp.

The journal fsyncs directory entries after creation and rotation. New journal frames preserve typed `details` and original field presence in the binary envelope, so domain registration and stable-ID retries survive replay. The updated reader accepts older envelopes and legacy Parquet archives; older readers do not understand the extended envelope, so upgrade the reader before writing the new format. Metadata omitted from historical registration events cannot be reconstructed. Each journal path requires one owning process; see [local journal ownership](../consensus/ordering.md#local-journal-ownership).

Journal directory walks and file opens reject symlinks using directory descriptors and no-follow flags.

## Related

* [Adapters Module](./adapters.md)
* [Core Module](./core.md)
* [Ordering](../consensus/ordering.md)
