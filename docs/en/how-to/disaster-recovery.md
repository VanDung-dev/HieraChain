---
title: "Durability and Disaster Recovery"
description: "How HieraChain protects pending events and resumes consensus after interruptions."
icon: material/backup-restore
---

# Durability and disaster recovery

The repository provides event journaling and consensus view changes. Database
backups, filesystem snapshots, key recovery, and infrastructure scaling remain
deployment responsibilities.

## 1. Event journaling

`TransactionJournal` records pending events before they enter the ordering
service. This protects events from application crashes or abrupt shutdowns.

Each event is synchronously appended and fsynced before it is queued. Fsync is
always enabled and cannot be disabled through configuration. On startup,
recovery replays journal entries and commits recovered events to block storage
before the Ordering Service becomes active. An incomplete final frame in the
active journal is truncated before new entries are appended. A complete frame
with corrupt Arrow data fails recovery; replay, certification, or
block-processing errors keep the Ordering Service in `MAINTENANCE` until
recovery succeeds.

Check `GET /api/ledger/ready` during startup. It returns HTTP 200 when every
registered Sub-Chain's Ordering Service is `ACTIVE`, and HTTP 503 while any
service is recovering or in maintenance.

```python
from hierachain.error_mitigation.journal import TransactionJournal

journal = TransactionJournal(storage_dir="data/journal")
journal.log_event(event_dict)
```

## 2. Consensus restart behavior

`BFTConsensus` uses `BFTViewChangeManager` when the current leader fails or a
view-change timeout expires. The manager coordinates the quorum and installs a
new view so consensus can continue without a separate recovery engine.

## 3. Deployment recovery responsibilities

The application deployment must provide and verify:

- database and filesystem backups;
- key backup and restoration procedures;
- snapshot retention and rollback policy;
- node replacement and infrastructure scaling.

These operations are intentionally not exposed as automatic classes in
`hierachain.error_mitigation`.

## Related

- [Error Handling and Recovery](../workflows/error-recovery.md)
- [Error Mitigation Module](../modules/error-mitigation.md)
- [Chain Rehydration](../workflows/chain-rehydration.md)
