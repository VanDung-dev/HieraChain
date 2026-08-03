---
title: "BFT Consensus"
description: "Byzantine Fault Tolerant (PBFT) consensus flow for adversarial environment block finalization."
icon: material/shield-key
---

# BFT Consensus

## Overview

The **Byzantine Fault-Tolerant (BFT)** consensus mechanism runs 3-phase PBFT when blocks are finalized. It requires `n ≥ 3f + 1` nodes to tolerate `f` faulty or malicious nodes. This replaces the `finalize_block()` step in Event Submission for BFT mode.

For PoA and PoF consensus flows, see [Consensus Mechanisms](./consensus_mechanisms.md).

**Requirement**: Minimum 4 nodes to tolerate 1 Byzantine failure (n=4, f=1: 3×1+1=4).

---

## Flow Diagram: 3-Phase PBFT

```mermaid
sequenceDiagram
    autonumber
    participant OS as ⚙️ OrderingService
    participant L as 👑 Leader Node
    participant admin as 🖥️ Validator 1
    participant business as 🖥️ Validator 2
    participant Vf as 🖥️ Validator f

    OS->>L: Events batch ready → trigger consensus

    rect rgb(0, 0, 0, 0)
        Note over L,Vf: PHASE 1 — PRE-PREPARE
        L->>L: Assign sequence number, create PRE-PREPARE message
        L->>admin: PRE-PREPARE(view, seq, block_digest)
        L->>business: PRE-PREPARE(view, seq, block_digest)
        L->>Vf: PRE-PREPARE(view, seq, block_digest)
    end

    rect rgb(0, 0, 0, 0)
        Note over L,Vf: PHASE 2 — PREPARE
        ledger->>ledger: Validate PRE-PREPARE, broadcast PREPARE
        ledger->>L: PREPARE(view, seq, digest)
        ledger->>business: PREPARE(view, seq, digest)
        business->>L: PREPARE(view, seq, digest)
        business->>ledger: PREPARE(view, seq, digest)
        Note over L: Collect 2f PREPARE votes
    end

    rect rgb(0, 0, 0, 0)
        Note over L,Vf: PHASE 3 — COMMIT
        L->>ledger: COMMIT(view, seq, digest)
        L->>business: COMMIT(view, seq, digest)
        ledger->>L: COMMIT(view, seq, digest)
        business->>L: COMMIT(view, seq, digest)
        Note over L: Collect 2f+1 COMMIT votes → finalize
        L->>L: Finalize & sign block
        L->>OS: Block committed → push to commit_queue
    end
```

---

## Flow Diagram: View Change (Leader Failure)

```mermaid
sequenceDiagram
    autonumber
    participant ledger as 🖥️ Validator 1
    participant VM as 🔄 BFTViewChangeManager
    participant NEW as 👑 New Leader

    Note over ledger: Leader timeout detected (no PRE-PREPARE received)

    ledger->>VM: trigger_view_change(current_view, failed_leader)
    VM->>VM: view += 1
    VM->>VM: Broadcast VIEW-CHANGE to all validators
    VM->>VM: Collect f+1 VIEW-CHANGE votes
    VM->>NEW: Elect new leader: Validators[new_view % n]
    NEW->>NEW: Broadcast NEW-VIEW message
    NEW->>NEW: Restart from Phase 1 — PRE-PREPARE
```

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **PRE-PREPARE** | Leader assigns sequence number and broadcasts block digest to all validators |
| **PREPARE** | Each validator validates the PRE-PREPARE, then broadcasts its own PREPARE vote. Leader collects 2f votes |
| **COMMIT** | Leader broadcasts COMMIT. Each node collects 2f+1 COMMIT votes, then finalizes locally |
| **View Change** | If leader silent > timeout: validators increment `view`, elect `Validators[view % n]` as new leader |

---

## Consensus Comparison

| Algorithm | Mechanism | Fault Tolerance | Use Case |
|:----------|:----------|:----------------|:---------|
| **PoA** | Identity-based, authority signs | Validator reputation | Private / internal networks |
| **PoF** | Rotating leader, quorum `height % n` | Distributed trust | Consortium / multi-org |
| **BFT** | 3-phase PBFT | Up to `f` Byzantine nodes in `3f+1` | Critical / adversarial environments |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| Leader timeout | View Change triggered, new leader elected (`Validators[new_view % n]`) |
| Validator sends invalid digest | Vote discarded, not counted toward quorum |
| Network partition < f nodes | Protocol continues if quorum (2f+1) still reachable |
| Network partition ≥ f+1 nodes | Protocol halts until partition heals (safety over liveness) |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| 3-Phase PBFT | `BFTConsensus.run_consensus()` | `consensus/bft/consensus.py` |
| PRE-PREPARE | `BFTConsensus._send_pre_prepare()` | `consensus/bft/consensus.py` |
| PREPARE collect | `BFTConsensus._handle_prepare()` | `consensus/bft/consensus.py` |
| COMMIT finalize | `BFTConsensus._handle_commit()` | `consensus/bft/consensus.py` |
| View Change | `BFTViewChangeManager.trigger_view_change()` | `consensus/bft/consensus.py` |
| Transport | `ZmqTransport.send()` / `receive()` | `network/zmq_transport.py` |

---

## Related

- [Consensus Mechanisms](./consensus_mechanisms.md): PoA and PoF details
- [Event Submission](./event-submission.md): BFT replaces the `finalize_block()` step
- [Error Mitigation](./error-recovery.md): handles leader failure recovery at system level
