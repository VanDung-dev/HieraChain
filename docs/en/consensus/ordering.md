---
title: "Ordering Service"
description: "Event ordering service: Deterministic ordering, Crash Fault Tolerance, and Journaling integration."
icon: material/order-bool-ascending
---

# Ordering Service (`hierachain/consensus/ordering/*`)

## Overview

**Ordering Service** is the central component in HieraChain's consensus architecture, responsible for receiving raw events, ordering them in a unique sequence, and packaging them into blocks. This is a **Crash Fault Tolerance (CFT)** mechanism, ensuring the system remains stable when some nodes go down.

---

## System Architecture

Ordering Service is designed using the **Facade** pattern, coordinating multiple specialized components:

| Component | Role | File |
| :--- | :--- | :--- |
| **OrderingService** | Main access point, lifecycle and configuration management. | `service.py` |
| **Processor** | Async processing, event flow coordination. | `processor.py` |
| **Block Builder** | Event batching and block structure construction. | `block_builder.py` |
| **Certifier** | Validates event signatures and permissions before ordering. | `certifier.py` |
| **Storage** | Manages persistent storage for pending events. | `storage.py` |
| **Recovery** | Restores state from **Event Journal** after failures. | `recovery.py` |

---

## Event Processing Flow (Ordering Pipeline)

```mermaid
graph TD
    A[Client Submit Event] --> B[Event Journal]
    B --> C[Event Pool]
    C --> D[Event Certifier]
    D -- Valid --> E[Ordering Processor]
    E --> F[Block Builder]
    F -- Batch Full / Timeout --> G[Block Creation]
    G --> H[Commit to Storage]
    H --> I[Notify Listeners]
```

---

## Core Features

### 1. Persistence & Durability
Accepted events are synchronously written to the **Event Journal** and fsynced before they are queued. Fsync is always enabled and cannot be disabled through configuration. On restart, `Recovery` replays journal entries and commits recovered events to block storage before the ordering service becomes active. An incomplete final frame in the active journal is truncated before the file is reopened for append. A complete frame with corrupt Arrow data fails recovery, and replay, certification, or block-processing errors leave the service in `MAINTENANCE` rather than activating with events missing.

The `GET /api/ledger/ready` endpoint returns HTTP 200 only when every registered Sub-Chain's Ordering Service is `ACTIVE`; it returns HTTP 503 while any service is recovering or in maintenance.

`lockdown()` waits for any in-flight commit to finish, then blocks further commits and incoming events until `resume()`. Queued events and an already cut batch remain available for resume; their journal entries are retained for crash recovery. Recovery completion does not override `LOCKDOWN`, and `resume()` cannot reactivate a stopped service.

### 2. Batching Strategy
Queue admission waits at most `enqueue_timeout` seconds (default `1.0`, allowed range greater than zero through `60`). A full queue or shutdown raises `OrderingBackpressureError`, carrying `event_id` and `journaled`. New submissions reserve capacity before writing, so rejection at this boundary has `journaled=False`. Reconciliation of an existing durable event reports `journaled=True` and can retry the same ID without another append. `POST /api/ledger/chains/{chain_name}/events` maps this error to HTTP 503 with these fields in `detail`. Shutdown wakes waiting producers. Admission holds the queue condition through fsync; disk latency therefore also delays consumers.

To optimize performance, Ordering Service does not create a block for each individual event but uses batching:
*   A directly initialized `OrderingService` uses `batch_size=100` and `batch_timeout=2.0` seconds by default.
*   Sub-Chain defaults are `block_size=50` and `batch_timeout=1.0` second.

### 3. Event Certification
The `Certifier` module integrates closely with the **Security** system to check:
*   Data format (Schema Validation).
*   Submitter's digital signature (Identity Verification).
*   Channel access permissions (Policy Enforcement).

The certifier retains the most recent 10,000 results by default (`EventCertifier(max_history=...)`). Rejected events leave the pending map. After a result is evicted, `get_event_status()` queries durable storage for committed events and returns `ordered` without a certification result; an older rejected event can return `None`. This history is not durable certification evidence.

---

## Usage Example

```python
from hierachain.consensus.ordering.service import OrderingService

# Initialize with enterprise configuration
config = {
    "batch_size": 200,
    "batch_timeout": 1.5,
    "storage_dir": "/data/ordering"
}

service = OrderingService(config=config)

# Submit event; the returned ID acknowledges journaling and enqueueing, not block finality
event_id = service.receive_event(
    event_data={"item": "container_45", "status": "shipped"},
    channel_id="logistics_chain",
    submitter_org="ORG_SUPPLY"
)
```

---

## Related

*   [Journal System](../modules/error-mitigation.md)
*   [Block Structure](../modules/core.md)
*   [BFT Consensus](./bft_consensus.md)
