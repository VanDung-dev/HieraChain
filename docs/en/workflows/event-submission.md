---
title: "Event Submission"
description: "Details of the core ingestion pipeline: event submission, validation, ordering, batching, and block appending."
icon: material/tray-arrow-down
---

# Event submission

## Overview

The Ledger API validates each event request. `SubChain.add_event()` then sends the event to `OrderingService`, which journals and queues it before returning `event_id`. The ID confirms acceptance for ordering; block commitment happens later. A background processor certifies and batches events, builds blocks, and puts them in the commit queue. The Sub-Chain consumer finalizes and persists each block. By default, Sub-Chain batches 50 events and waits 1.0 second before creating a block. Configure Main-Chain consensus separately with `HRC_MAINCHAIN_CONSENSUS`.

For PoA and PoF diagrams, see [Consensus Mechanisms](./consensus_mechanisms.md).

---

## Flow diagram

```mermaid
sequenceDiagram
    autonumber
    participant Client as 🖥️ Client / ERP
    participant API as 🌐 FastAPI
    participant SC as 📦 SubChain
    participant OS as ⚙️ OrderingService
    participant BM as 🧱 OrderingBlockManager
    participant PRF as 🔐 Proof
    participant DB as 💾 Storage

    rect rgb(0, 0, 0, 0)
        Note over Client,API: Phase 1 — Request and asynchronous acknowledgement
        Client->>API: POST /api/ledger/chains/{chain_name}/events
        API->>SC: add_event(event_dict)
        SC->>OS: receive_event(event_data, channel_id, submitter_org)
        OS->>OS: Append to Event Journal
        OS->>OS: Enqueue in event_pool
        API-->>Client: 200 OK (event_id accepted for ordering)
    end

    rect rgb(0, 0, 0, 0)
        Note over OS: Phase 2 — Background certification and batching
        OS->>OS: Certify event
        OS->>OS: BlockBuilder.add_event()
        Note over OS: Batch size or timeout returns a batch of event data
        OS->>BM: create_block_async(raw_event_data)
        BM->>BM: Build Block
        BM->>BM: commit_block()
        Note over BM: Persist ordered block and enqueue it in commit_queue
    end

    rect rgb(0, 0, 0, 0)
        Note over SC: Phase 3 — Asynchronous finalization and persistence
        Note over SC: Background consumer processes the commit_queue

        SC->>OS: get_next_block()
        OS-->>SC: Block
        SC->>SC: Set block index and hash links
        SC->>PRF: finalize_block(block, chain_name)
        PRF-->>SC: Finalized block
        SC->>DB: Persist finalized block
        SC->>SC: Add block to Sub-Chain
        SC->>SC: auto_submit_proof_if_needed()

        Note over SC: → Triggers Proof Anchoring
    end
```

---

## Step-by-step breakdown

| Step | Description |
|:-----|:------------|
| **1. API receive** | `POST /api/ledger/chains/{chain_name}/events` validates the request schema and passes the event to the Sub-Chain |
| **2. Enqueue** | `SubChain.add_event()` supplies missing internal defaults, then calls `OrderingService.receive_event()`; the orderer journals the event before queueing it and returns an `event_id` |
| **3. Background certification** | The Ordering Service processes queued events through its certifier; this occurs after the API acknowledgement |
| **4. Batch** | `BlockBuilder.add_event()` adds certified events to a batch; size, timeout, or an explicit flush returns the batch data |
| **5. Build and order commit** | `OrderingBlockManager.create_block_async()` builds a `Block`; `commit_block()` persists the ordering block and puts it in `commit_queue` |
| **6. Sub-Chain finalization** | The consumer dequeues the block, sets its index and hash links, then calls the configured `finalize_block()` implementation (PoA by default) |
| **7. Chain persistence** | The finalized block is saved through the configured storage handler and added to the Sub-Chain |
| **8. Proof trigger** | `auto_submit_proof_if_needed()` may submit a proof to the Main Chain when its configured threshold is met |

---

## Event structure

```python
event = {
    "entity_id": "product-SKU-001",    # Domain entity identifier
    "event_type": "quality_check",      # Event type (domain-specific)
    "timestamp": 1714000000.0,
    "details": {                        # Domain-specific payload
        "check_type": "visual",
        "check_result": "passed",
        "inspector": "station-7"
    }
}
```

> The Ledger API requires `entity_id` and `event_type`, and maps `event_type` to the internal `event` field. Defaults in `SubChain.add_event()` apply to internal calls and do not make those API fields optional. `SubChain.add_event()` does not run a forbidden-term scan before enqueueing; API validation and background certification occur at their respective stages. The returned `event_id` acknowledges acceptance for ordering, not block finalization.

---

## Error handling

| Condition | Behavior |
|:----------|:---------|
| Request body is invalid | FastAPI rejects it during request-model validation before calling `SubChain.add_event()` |
| Journal write fails | `OrderingService.receive_event()` raises before adding the event to its in-memory queue |
| Event fails background certification | The processor marks the event rejected; it is not added to a block |
| Ordering block persistence fails | The error is logged and the Ordering Service enters `MAINTENANCE`; the block is not added to `commit_queue` |
| Block finalization or persistence fails | The Sub-Chain consumer logs the error and continues its loop; the dequeued block is not explicitly requeued by that loop |

---

## Key classes and methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Receive event | `SubChain.add_event()` | `hierachain/hierarchical/sub_chain/base.py` |
| Journal, queue, and order | `OrderingService.receive_event()` | `hierachain/consensus/ordering/service.py` |
| Certify and batch events | `OrderingProcessor` and `BlockBuilder.add_event()` | `hierachain/consensus/ordering/processor.py`, `hierachain/consensus/ordering/block_builder.py` |
| Build and commit ordering block | `OrderingBlockManager.create_block_async()` / `commit_block()` | `hierachain/consensus/ordering/block_manager.py` |
| Finalize and persist Sub-Chain block | `_process_and_finalize_single_block()` | `hierachain/hierarchical/sub_chain/block.py` |
| Storage adapters | Database adapters | `hierachain/adapters/database/` |

---

## Related

- [Consensus Mechanisms](./consensus_mechanisms.md): PoA and PoF sub-diagrams
- [Proof Anchoring](./proof-anchoring.md): triggered after block finalized
- [BFT Consensus](./bft-consensus.md): full 3-phase PBFT flow
- [Policy Enforcement](./policy-enforcement.md): gates access before `add_event()`
- [MSP Identity](./msp-identity.md): `authorize_action()` called before submission
