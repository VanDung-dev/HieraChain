---
title: "Cluster Lockdown"
description: "Coordinated cluster lockdown protocol triggered by critical risk detection to freeze the system state."
icon: material/lock
---

# Cluster Lockdown & Recovery

## Overview

The **Cluster Lockdown Protocol** coordinates a system-wide state freeze across all nodes when a critical anomaly is detected. It uses **gossip-style P2P messaging over ZeroMQ** and requires a **2/3 quorum** of registered nodes to trigger both lockdown and recovery. All messages are authenticated with **HMAC-SHA256** to prevent spoofed lockdown attacks.

**Key property**: No single node can lock the cluster unilaterally — quorum is mandatory.

---

## Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant N1 as 🖥️ Node 1 (Detector)
    participant N2 as 🖥️ Node 2
    participant N3 as 🖥️ Node 3
    participant OS as ⚙️ Local OrderingService

    Note over N1: Risk Analyzer detects anomaly

    rect rgb(0, 0, 0, 0)
        Note over N1,N3: PHASE 1 — LOCKDOWN VOTING
        N1->>N1: broadcast_lockdown_vote(reason)
        N1->>N2: LOCKDOWN_VOTE { node_id, reason, HMAC-SHA256 }
        N1->>N3: LOCKDOWN_VOTE { node_id, reason, HMAC-SHA256 }

        N2->>N2: Verify HMAC signature & timestamp (≤300s)
        N2->>N2: Register lockdown vote
        N2->>N1: LOCKDOWN_VOTE (N2 agrees)
        N2->>N3: LOCKDOWN_VOTE (N2 agrees)

        N3->>N3: _check_lockdown_quorum() → votes/total ≥ 0.66
        N3->>N3: _trigger_quorum_lockdown()
    end

    rect rgb(0, 0, 0, 0)
        Note over N1,OS: PHASE 2 — SYSTEM FREEZE
        N1->>OS: local_lockdown_callback()
        N2->>OS: local_lockdown_callback()
        N3->>OS: local_lockdown_callback()
        OS->>OS: Halt event acceptance
        N1->>N2: QUARANTINE_REPORT (pending_event_ids, last_block_hash)
        N1->>N3: QUARANTINE_REPORT (pending_event_ids, last_block_hash)
    end

    rect rgb(0, 0, 0, 0)
        Note over N1,OS: PHASE 3 — RECOVERY VOTING
        N1->>N2: RECOVERY_VOTE
        N1->>N3: RECOVERY_VOTE
        N2->>N3: RECOVERY_VOTE

        N3->>N3: _check_recovery_quorum() → ≥ 0.66
        N3->>N3: _trigger_quorum_recovery()
        N1->>OS: local_recovery_callback()
        N2->>OS: local_recovery_callback()
        N3->>OS: local_recovery_callback()
        OS->>OS: Resume event acceptance
    end
```

---

## State Machine

```mermaid
stateDiagram-v2
    [*] --> NORMAL
    NORMAL --> VOTING: Anomaly detected
    VOTING --> LOCKED: Quorum ≥ 2/3 lockdown votes
    VOTING --> NORMAL: Votes insufficient / timeout
    LOCKED --> RECOVERING: Quorum ≥ 2/3 recovery votes
    RECOVERING --> NORMAL: State sync complete
    LOCKED --> LOCKED: Quarantine reports exchanged
```

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Anomaly detection** | `RiskAnalyzer` or manual operator triggers `broadcast_lockdown_vote(reason)` |
| **2. Vote broadcast** | Gossip LOCKDOWN_VOTE to all peers, signed with HMAC-SHA256 + timestamp |
| **3. Vote verification** | Each receiver validates HMAC and rejects votes older than 300 seconds |
| **4. Quorum check** | `_check_lockdown_quorum()`: if `votes / total_nodes ≥ 0.66` → lockdown triggered |
| **5. System freeze** | Each node calls `local_lockdown_callback()` → `OrderingService` halts event acceptance |
| **6. Quarantine reports** | Nodes exchange pending event IDs and last block hashes to audit state divergence |
| **7. Recovery voting** | After investigation, operator or auto-trigger initiates `RECOVERY_VOTE` gossip |
| **8. Recovery quorum** | Same 2/3 threshold required. On quorum: `local_recovery_callback()` → resume |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| HMAC verification fails | Vote discarded, warning logged |
| Vote timestamp > 300s old | Vote rejected (replay protection) |
| Lockdown quorum never reached | System continues operating normally, votes expire |
| Recovery quorum never reached | Cluster stays locked; escalation alert sent via Risk Alerts |
| Node joins during lockdown | New node receives LOCKED state via `StateSyncManager` |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Initiate lockdown | `ClusterLockdownManager.broadcast_lockdown_vote()` | `cluster/cluster_lockdown.py` |
| Verify vote | `_verify_lockdown_message()` | `cluster/cluster_lockdown.py` |
| Quorum check | `_check_lockdown_quorum()` | `cluster/cluster_lockdown.py` |
| System freeze | `local_lockdown_callback()` | `cluster/cluster_lockdown.py` |
| Recovery quorum | `_check_recovery_quorum()` | `cluster/cluster_lockdown.py` |
| State sync | `StateSyncManager.sync_state()` | `cluster/state_sync.py` |
| Transport | `ZmqTransport.broadcast()` | `network/zmq_transport.py` |

---

## Related

- [Risk Analysis & Alerts](./risk-alerts.md) — risk threshold breach triggers this workflow
- [Error Mitigation](./error-recovery.md) — handles state rollback after recovery
- [Key Backup](./key-backup.md) — lockdown may trigger key rotation → Key Backup & Restoration
