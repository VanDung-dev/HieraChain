---
title: "Ordering Service"
description: "Local event ordering, durable journal recovery, certification, batching and signed block persistence."
icon: material/order-bool-ascending
---

# Ordering Service (`hierachain/consensus/ordering/*`)

## Overview

Ordering Service receives local events, journals and queues them, then certifies and batches them into signed blocks. Journal replay supports recovery after a process failure. The service does not implement replicated orderer election or automatic node failover.

## System Architecture

Ordering Service is designed using the Facade pattern, coordinating multiple specialized components:

| Component | Role | File |
| :--- | :--- | :--- |
| OrderingService | Main access point, lifecycle and configuration management. | `service.py` |
| Processor | Async collection, batch signature verification, certification and event processing. | `processor.py` |
| Block Builder | Collects event batches; the block manager constructs blocks. | `block_builder.py` |
| Certifier | Runs custom rules, structure checks and conditional signature/ZK checks. | `certifier.py` |
| Storage | Persists signed blocks and reads finalized history. | `storage.py` |
| Recovery | Restores state from Event Journal after failures. | `recovery.py` |
| Journal lookup | Indexes durable ID/channel/content commitments for stable-ID admission. | `journal_lookup.py` |

`OrderingService` owns the event queue, pending events, certifier, block builder, storage and metrics. `OrderingProcessor` accesses these dependencies through the service and processes both live batches and replayed events directly. Block creation and commit remain in `OrderingBlockManager`; journal replay remains in `OrderingRecovery`.

## Event Processing Flow (Ordering Pipeline)

```mermaid
graph TD
    A[Client Submit Event] --> B[Event Journal]
    B --> C[Event Pool]
    C --> D[Event Certifier]
    D -- Valid --> E[Ordering Processor]
    E --> F[Block Builder]
    F -- Batch Full / Timeout --> G[Create Block and Run Configured Finalizer]
    G --> S[Sign Block Header]
    S --> H[Commit to Storage]
    H --> I[Commit Queue for Consumer]
```

## Core Features

### 1. Persistence & Durability
Accepted events are synchronously written to the Event Journal and fsynced before they are queued. Fsync is always enabled and cannot be disabled through configuration. On restart, `Recovery` replays journal entries and commits recovered events to block storage before the ordering service becomes active. An incomplete final frame in the active journal is truncated before the file is reopened for append. A complete frame with corrupt Arrow data fails recovery, and replay, certification, or block-processing errors leave the service in `MAINTENANCE` rather than activating with events missing.

The `GET /api/ledger/ready` endpoint returns HTTP 200 only when every registered Sub-Chain's Ordering Service is `ACTIVE`; it returns HTTP 503 while any service is recovering or in maintenance.

`TransactionJournal.log_event()` still flushes and fsyncs every successful append before returning. `read_since()` reads records from disk but reuses a successful sync when the active file's device, inode, size, modification time and change time match the synchronized state. Opening/closing the writer, rotation and failed writes invalidate that state. Unknown or changed state requires another fsync; read and sync failures propagate. An active path replaced with another inode is rejected. Explicit `flush()` continues to synchronize every call. These rules retain the single-owner append-only journal contract; they do not make read-back a memory-only ACK.

Stable IDs first check live pending/batch/processed state and block storage. For remaining IDs, `JournalEventLookup` scans journal history once on first use, then reads only the suffix after its cursor and stores compact channel/content commitments. It rejects conflicting IDs, including conflicting repeated records. An older journal-only event whose payload must be requeued still uses a full disk read; no historical payload copies are retained in the index. Custom or replaced journals without this lookup keep the compatibility scan. Missing/truncated cursor history fails closed. Initial scanning, archive enumeration and index metadata still grow with retained history; no retention/compaction is added.

`lockdown()` waits for any in-flight commit to finish, then blocks further commits and incoming events until `resume()`. Queued events and an already cut batch remain available for resume; their journal entries are retained for crash recovery. Recovery completion does not override `LOCKDOWN`, and `resume()` cannot reactivate a stopped service.

### 2. Batching Strategy
Queue admission waits at most `enqueue_timeout` seconds (default `1.0`, allowed range greater than zero through `60`). A full queue or shutdown raises `OrderingBackpressureError`, carrying `event_id` and `journaled`. New submissions reserve capacity before writing, so rejection at this boundary has `journaled=False`. Reconciliation of an existing durable event reports `journaled=True` and can retry the same ID without another append. `POST /api/ledger/chains/{chain_name}/events` maps this error to HTTP 503 with these fields in `detail`. Shutdown wakes waiting producers. Admission holds the queue condition through fsync; disk latency therefore also delays consumers.

To optimize performance, Ordering Service does not create a block for each individual event but uses batching:
*   A directly initialized `OrderingService` uses `batch_size=100` and `batch_timeout=2.0` seconds by default.
*   Sub-Chain defaults are `block_size=50` and `batch_timeout=1.0` second; explicit configuration can change both.

### 3. Event Certification
`EventCertifier` runs caller-added validation rules and checks required `entity_id`, `event` and a finite timestamp. Live events must be within 300 seconds of server time; replay can allow older timestamps. Its signature helper verifies only when string sender/signature fields and a string details payload are available, unless batch verification already succeeded. It also runs the optional ZK check. It does not call MSP or `PolicyEngine`; applications must enforce channel permissions in their integration.

The certifier retains the most recent 10,000 results by default (`EventCertifier(max_history=...)`). Rejected events leave the pending map. After a result is evicted, `get_event_status()` queries durable storage for committed events and returns `ordered` without a certification result; an older rejected event can return `None`. This history is not durable certification evidence.

### 4. Commit and cross-chain costs

`events_committed` and `average_batch_size` count only events in successfully persisted blocks. Latency uses the receipt times of those events; timing state for events still waiting in another batch is retained. Processor `batch_size` can differ from block `block_size` without counting uncommitted events.

Block index assignment, previous-hash linkage, signing and storage commitment remain serialized per Ordering Service. Signature verification retains the existing batch thread pool and certification checks. The 2PC coordinator keeps durable phase records and read-back before participant commits; uncertain COMMIT decisions remain in doubt and cannot trigger rollback. Reducing journal rereads does not remove these integrity boundaries or imply that an event acceptance ACK is block finality. Independent chains can partition load with separate journal owners; batching blocks does not batch event durability ACKs.

## Usage Example

Provision the complete signing identity and approved trusted keys using [Quickstart](../getting-started/quickstart.md), and select a supported durable storage backend before running this example. `batch_size` limits processor collection; `block_size` limits events per block. The returned ID confirms acceptance, while `force_block_creation()` requests a flush; inspect persisted blocks to confirm commitment.

```python
import time
from hierachain.consensus.ordering.service import OrderingService

config = {
    "batch_size": 200,
    "block_size": 100,
    "batch_timeout": 1.5,
    "storage_dir": "data/ordering-example",
}
service = OrderingService(config=config)
try:
    event_id = service.receive_event(
        event_data={
            "entity_id": "CONTAINER-45",
            "event": "shipped",
            "timestamp": time.time(),
            "details": {"status": "shipped"},
        },
        channel_id="logistics_chain",
        submitter_org="ORG_SUPPLY",
    )
    service.force_block_creation()
finally:
    service.shutdown()
```

## Local journal ownership {#local-journal-ownership}

A local journal path has one owning instance/process at a time, enforced by a nonblocking POSIX advisory writer lock. A second owner fails to open until the first closes or exits; this guard does not turn the journal into a shared multiwriter log. Multiple threads must share the same `TransactionJournal` instance. Give independent writers distinct node identities and storage directories, or separate local volumes on a filesystem that supports POSIX locks and directory fsync. The Kubernetes StatefulSet's per-pod PVC pattern keeps node journals separate. Upgrade every process using a path before writing the new journal format; older versions do not acquire the writer lock.

## Related

*   [Journal System](../modules/error-mitigation.md)
*   [Block Structure](../modules/core.md)
*   [BFT Consensus](./bft_consensus.md)
