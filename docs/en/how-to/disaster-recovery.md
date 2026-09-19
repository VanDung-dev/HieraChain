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

The journal uses a durable append-only format and exposes replay support for
rebuilding the pending event stream after restart.

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
