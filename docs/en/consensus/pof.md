---
title: "Proof of Federation (PoF)"
description: "Federation consensus protocol: Deterministic leader election, Quorum voting, and multi-organization governance."
icon: material/account-group-outline
---

# Proof of Federation (`hierachain/consensus/proof_of_federation.py`)

## Overview

**Proof of Federation (PoF)** is an Inter-MainChain consensus protocol designed specifically for **Consortium Alliance** networks. It enables multiple independent organizations (e.g., Hospital A, Hospital B, Insurance Z)—each operating their own autonomous MainChain—to securely exchange, verify, and reach consensus on cross-organizational event proofs **without requiring a central RootChain or single authority**.

---

## Architectural Position: PoA vs. PoF

| Consensus Mechanism | Scope & Purpose | Governance Model |
| :--- | :--- | :--- |
| **Proof of Authority (PoA)** | **Intra-Organization** (Single MainChain + Sub-Chains) | Designated Authority (Single-entity control within an enterprise) |
| **Proof of Federation (PoF)** | **Inter-Organization** (Peer-to-Peer MainChain Alliance) | Equal Multi-Party Federation (Threshold Quorum without central RootChain) |

---

## How It Works

PoF uses a peer-to-peer federation rotation model combined with multi-signature verification:
1.  **Leader Rotation**: The Leader with block proposal rights for a federation round is determined by a deterministic mathematical formula: `Leader = Validators[BlockIndex % TotalValidators]`. This prevents any single MainChain from monopolizing block creation.
2.  **Quorum Voting**: For a cross-organizational block to be valid across independent MainChains, it requires multi-signature confirmation from a minimum threshold of consortium members (typically **2/3 + 1**).
3.  **Sorted Validator List**: The list of participating MainChains is deterministically sorted across all nodes to guarantee schedule synchronization.

---

## Key Features

<div class="grid cards" markdown>

*   :material-account-group:{ .lg .middle } __Multi-party Governance__

    ---

    Eliminates Single Point of Failure. If the current Leader fails, block creation rights automatically transfer to the next node in the cycle.

*   :material-vote-outline:{ .lg .middle } __Quorum Voting__

    ---

    Provides an additional security layer by requiring consensus from the majority of member organizations before committing data.

*   :material-scale-balance:{ .lg .middle } __Fairness & Transparency__

    ---

    Every member organization has equal opportunity to contribute and control the ledger through the predetermined schedule.

</div>

---

## Configuration Parameters

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `min_validators` | Minimum number of nodes for network operation. | `3` |
| `block_interval` | Target block creation cycle. | `5.0` seconds |
| `enforce_rotation` | Mandatory leader rotation after each block. | `True` |

---

## Block Verification Flow

```mermaid
graph TD
    A[Block Proposed by Leader] --> B{Verify Leader Identity}
    B -- Correct Leader --> C[Collect Quorum Signatures]
    C --> D{Signatures >= 2/3 + 1?}
    D -- Yes --> E[Commit Block to Ledger]
    D -- No --> F[Reject & Wait for Next Leader]
    B -- Wrong Leader --> G[Reject Block]
```

---

## Advantages and Limitations

*   **Advantages**: Suitable for multi-party consortium networks, resistant to domination by a small group, high availability.
*   **Limitations**: Requires additional network bandwidth for Quorum signature collection compared to PoA, performance slightly degrades when the number of Validators grows too large.

---

## Related

*   [Proof of Authority (PoA)](./poa.md)
*   [P2P Network Architecture](../modules/network.md)
*   [Security System](../security/authorization-access-control.md)
