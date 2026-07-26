---
title: "Cross-Chain 2PC"
description: "Two-Phase Commit (2PC) protocol coordination for atomic cross-chain event operations."
icon: material/swap-horizontal
---

# Cross-Chain Operation (2PC)

## Overview

When a business operation needs to atomically span two Sub-Chains (e.g., an asset moves from the `logistics` chain to the `finance` chain), HieraChain uses the **Two-Phase Commit (2PC)** protocol to guarantee atomicity. Either both chains commit the change, or both roll back — no partial state is possible.

**Example real-world trigger**: An inventory item is transferred between departments. The source chain records a `deduct` event; the destination chain records a `receive` event. Both must succeed or neither applies.

---

## Flow Diagram — Happy Path

```mermaid
sequenceDiagram
    autonumber
    participant HM as 🏛️ HierarchyManager
    participant TM as 🔄 CrossChainOperationManager
    participant SRC as 📦 Source SubChain
    participant DST as 📦 Destination SubChain

    HM->>TM: initiate_cross_chain_operation(src, dst, payload)
    TM->>TM: Create CrossChainOperation (UUID, state=PENDING)

    rect rgb(0, 0, 0, 0)
        Note over TM,DST: PHASE 1 — PREPARE
        TM->>SRC: prepare_operation(op_id, payload, is_source=True)
        SRC->>SRC: Lock resources, validate payload
        SRC-->>TM: True ✅

        TM->>DST: prepare_operation(op_id, payload, is_source=False)
        DST->>DST: Verify capacity to accept
        DST-->>TM: True ✅

        TM->>TM: state = PREPARED
    end

    rect rgb(0, 0, 0, 0)
        Note over TM,DST: PHASE 2 — COMMIT
        TM->>SRC: commit_operation(op_id)
        SRC-->>TM: True ✅
        TM->>DST: commit_operation(op_id)
        DST-->>TM: True ✅
        TM->>TM: state = COMMITTED
    end

    TM-->>HM: op_id (COMMITTED)
```

---

## Flow Diagram — Failure Paths

```mermaid
sequenceDiagram
    autonumber
    participant TM as 🔄 CrossChainOperationManager
    participant SRC as 📦 Source SubChain
    participant DST as 📦 Destination SubChain

    rect rgb(0, 0, 0, 0)
        Note over TM,DST: SCENARIO A — Phase 1 Prepare Fails
        TM->>SRC: prepare_operation(op_id, payload)
        SRC-->>TM: True ✅
        TM->>DST: prepare_operation(op_id, payload)
        DST-->>TM: False ❌  (capacity / validation fail)
        TM->>TM: state = PENDING → rollback triggered
        TM->>SRC: rollback_operation(op_id)
        TM->>DST: rollback_operation(op_id)
        TM->>TM: state = ROLLED_BACK ⚠️
    end

    rect rgb(0, 0, 0, 0)
        Note over TM,DST: SCENARIO B — Phase 2 Partial Commit Fails
        TM->>SRC: commit_operation(op_id)
        SRC-->>TM: True ✅
        TM->>DST: commit_operation(op_id)
        DST-->>TM: Exception ❌
        TM->>TM: state = FAILED ❌
        Note over TM: Manual reconciliation required<br/>Inspect logs for partial state
    end
```

---

## Operation State Machine

```mermaid
flowchart LR
    P["PENDING"] --> PR["PREPARED"]
    PR --> C["COMMITTED ✅"]
    PR --> RB["ROLLED_BACK ⚠️"]
    P --> F["FAILED ❌"]
    PR --> F
```

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Initiate** | `HierarchyManager` creates a `CrossChainTransaction` with UUID and `state=PENDING` |
| **2. Phase 1 — Prepare SRC** | Source chain locks resources, validates payload schema |
| **3. Phase 1 — Prepare DST** | Destination chain checks capacity and constraints |
| **4. Phase 1 result** | If both return `True`: state → `PREPARED`. If either fails: immediate rollback on both |
| **5. Phase 2 — Commit SRC** | Source chain finalizes the operation (emits event via Event Submission) |
| **6. Phase 2 — Commit DST** | Destination chain finalizes (emits event via Event Submission) |
| **7. Result** | State → `COMMITTED`. `tx_id` returned to caller |

---

## Error Handling

| Condition | State | Recovery |
|:----------|:------|:---------|
| Phase 1 fails on SRC | `ROLLED_BACK` | Automatic rollback on DST |
| Phase 1 fails on DST | `ROLLED_BACK` | Automatic rollback on SRC |
| Phase 2 commit fails on either | `FAILED` | Manual reconciliation via audit log |
| Network timeout during Phase 2 | `FAILED` | Operator must inspect last committed state |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Initiate | `HierarchyManager.initiate_cross_chain_transaction()` | `hierarchical/hierarchy_manager.py` |
| Create transaction | `CrossChainTransactionManager.__init__()` | `domains/generic/chains/domain_chain.py` |
| Prepare | `DomainChain.prepare_transaction()` | `domains/generic/chains/domain_chain.py` |
| Commit | `DomainChain.commit_transaction()` | `domains/generic/chains/domain_chain.py` |
| Rollback | `DomainChain.rollback_transaction()` | `domains/generic/chains/domain_chain.py` |

---

## Related

- [Event Submission](./event-submission.md) — each `commit_transaction()` internally calls `add_event()`
- [Error Mitigation](./error-recovery.md) — handles state rollback at the system level
