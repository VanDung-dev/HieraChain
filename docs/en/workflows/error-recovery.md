---
title: "Error Mitigation & Recovery"
description: "Automated recovery and mitigation workflows for network failures, leader timeouts, or integrity anomalies."
icon: material/alert-decagram
---

# Error Mitigation & Recovery

## Overview

HieraChain provides layered, automated recovery mechanisms across three dimensions: **network resilience**, **consensus leader recovery**, and **state rollback**. These operate independently and can be active simultaneously.

---

## 6A — Network Recovery

```mermaid
flowchart TB
    NET["🌐 Network Issue Detected"]
    LAT["📊 Collect Latency History"]
    ADJ["⏱️ adjust_timeout()\nRecalculate based on avg + max latency"]
    RED["📡 send_with_redundancy()\nSend via N parallel paths simultaneously"]
    FIRST["✅ First successful response wins"]
    PART["⚠️ Partition Detected?\navg_latency > 5000ms"]
    VC["🔄 _initiate_view_change()\nTrigger BFT view change"]

    NET --> LAT --> ADJ --> RED --> FIRST
    RED --> PART
    PART -->|Yes| VC
    PART -->|No| FIRST
```

**Strategy**: `send_with_redundancy()` dispatches the same message over N parallel network paths simultaneously. The first successful response wins and remaining in-flight calls are cancelled. This handles intermittent path failures without explicit retry logic.

---

## 6B — Consensus Recovery (Leader Failure)

```mermaid
sequenceDiagram
    autonumber
    participant CRE as 🔧 ConsensusRecoveryEngine
    participant VM as 🔄 BFTViewChangeManager
    participant NEW as 👑 New Leader

    Note over CRE: Leader timeout detected
    CRE->>CRE: handle_leader_failure(failed_leader_id, current_view)
    CRE->>CRE: Check recovery_attempts < max (default 3)
    CRE->>VM: _initiate_view_change(failed_leader, new_view = view + 1)
    VM->>VM: Broadcast VIEW-CHANGE to all validators
    VM->>NEW: Elect new leader: Validators[new_view % n]
    NEW->>NEW: Restart PRE-PREPARE phase
    CRE->>CRE: Clear recovery_attempts on success
```

---

## 6C — State Rollback

```mermaid
flowchart LR
    ERR["❌ Critical Error\nor Integrity Failure"]
    SNAP["📸 Load Snapshot\n(RollbackManager)"]
    JRNL["📓 Replay Journal\n(TransactionJournal)"]
    VER["🔍 Validate Restored State\n(DataValidator)"]
    OK["✅ State Restored"]
    ALERT["🚨 Alert + Escalate\n(AlertManager)"]

    ERR --> SNAP --> JRNL --> VER
    VER -->|Valid| OK
    VER -->|Invalid| ALERT
```

**Rollback steps**:
1. `RollbackManager.load_snapshot()` — load the most recent consistent snapshot
2. `TransactionJournal.replay()` — replay committed journal entries since the snapshot
3. `DataValidator.validate()` — verify the restored state against cryptographic checksums
4. If validation fails: escalation alert sent via Risk Alerts; manual intervention required

---

## Step-by-Step Breakdown

| Sub-flow | Trigger | Action |
|:---------|:--------|:-------|
| **6A Network** | `avg_latency > threshold` | Adaptive timeout + parallel redundant send |
| **6A Partition** | `avg_latency > 5000ms` | Trigger BFT View Change (BFT Consensus) |
| **6B Leader** | `leader_timeout` | `ConsensusRecoveryEngine.handle_leader_failure()` → View Change |
| **6B Max retries** | `recovery_attempts ≥ max` | Log critical error, alert, halt consensus |
| **6C Rollback** | Integrity failure or critical error | Snapshot → Journal replay → Validate |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| All recovery paths exhausted (6B) | Critical alert sent, node halts consensus participation |
| Snapshot not found (6C) | Full rehydration from DB (Chain Rehydration) attempted |
| Journal replay produces invalid state (6C) | Alert escalated via Risk Alerts, manual intervention flagged |
| Network partition heals | Adaptive timeout reduces automatically, normal flow resumes |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Network adaptive timeout | `NetworkRecoveryManager.adjust_timeout()` | `error_mitigation/recovery_engine.py` |
| Redundant send | `send_with_redundancy()` | `error_mitigation/recovery_engine.py` |
| Leader failure | `ConsensusRecoveryEngine.handle_leader_failure()` | `error_mitigation/recovery_engine.py` |
| View change trigger | `BFTViewChangeManager._initiate_view_change()` | `consensus/bft/consensus.py` |
| Snapshot load | `RollbackManager.load_snapshot()` | `error_mitigation/rollback_manager.py` |
| Journal replay | `TransactionJournal.replay()` | `error_mitigation/journal.py` |
| State validate | `DataValidator.validate()` | `error_mitigation/validator.py` |

---

## Related

- [BFT Consensus](./bft-consensus.md) — View Change detail
- [Cluster Lockdown](./cluster-lockdown.md) — cluster-level recovery
- [Chain Rehydration](./chain-rehydration.md) — full chain reload from DB
- [Risk Analysis & Alerts](./risk-alerts.md) — escalation notifications
