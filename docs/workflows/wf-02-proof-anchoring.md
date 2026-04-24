# WF-2: Proof Anchoring

**Group**: A — Core Chain Operations
**Trigger**: `SubChain.auto_submit_proof_if_needed()` after block finalized (WF-1 step 9)
**Output**: Cryptographic proof hash stored on Main Chain; raw event data never exposed at root level
**Key modules**: `hierarchical/sub_chain.py`, `hierarchical/main_chain.py`, `security/zk_prover.py`

> [← WF-1: Event Submission](./wf-01-event-submission.md) · [Back to Overview](../ARCHITECTURE.md) · [WF-3: Cross-Chain 2PC →](./wf-03-cross-chain-2pc.md)

---

## Overview

After a block is finalized on a Sub-Chain, the Sub-Chain submits a **cryptographic proof** (hash + optional ZK proof) to the Main Chain. The Main Chain stores only the proof — never raw event data. This is how global immutability is enforced without storing sensitive domain data on the root chain.

This is a **post-block trigger**, not a user-initiated call. It fires automatically when `chain_length % proof_interval == 0`.

---

## Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant SC as 📦 SubChain
    participant ZKP as 🔐 ZKProver
    participant MC as 🔗 MainChain

    SC->>SC: auto_submit_proof_if_needed()
    SC->>SC: Check: chain length > 1 AND block finalized

    alt ZK Proofs Enabled (HRC_ENABLE_ZK_PROOFS=true)
        SC->>ZKP: generate_proof(old_state_root, new_state_root, block_index, events)
        ZKP->>ZKP: Compute proof (Mock SHA-256 or ZoKrates circuit)
        ZKP-->>SC: ProofResult { proof: bytes, success: bool }
        SC->>SC: Retry up to 3× with exponential backoff on failure
    else ZK Proofs Disabled
        SC->>SC: zk_proof = None
    end

    SC->>SC: _generate_default_proof_metadata()
    SC->>MC: add_proof(sub_chain_name, proof_hash, metadata, zk_proof)
    MC->>MC: Verify ZK proof (if enabled)
    MC->>MC: Store proof block on Main Chain
    MC-->>SC: True (success)

    SC->>SC: Record proof_submitted event
    SC->>SC: Update last_proof_submission timestamp
```

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Trigger check** | `auto_submit_proof_if_needed()` checks `len(chain) > 1` and block has been finalized |
| **2. ZK generation** | If `HRC_ENABLE_ZK_PROOFS=true`: ZKProver computes over `(old_state_root, new_state_root, events)`. Retries 3× with backoff |
| **3. Proof metadata** | `_generate_default_proof_metadata()` builds `{ sub_chain_name, block_count, latest_hash, timestamp }` |
| **4. Main Chain write** | `MainChain.add_proof()` verifies ZK proof, appends a new proof block |
| **5. Record** | Sub-Chain logs a `proof_submitted` internal event and updates `last_proof_submission` |

---

## ZK Proof Modes

| Mode | Mechanism | Use Case |
|:-----|:----------|:---------|
| `mock` | SHA-256 hash simulation | Development / Testing |
| `production` | ZoKrates ZK-SNARKs circuits | Production deployment |

---

## Configuration

| Setting | Default | Description |
|:--------|:--------|:------------|
| `HRC_ENABLE_ZK_PROOFS` | `false` | Toggle ZK verification |
| `HRC_ZK_MODE` | `mock` | `mock` or `production` |
| `HRC_ZK_PROOF_REQUIRED_FOR_MAINCHAIN` | `false` | Block proof submission if ZK fails |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| ZK proof generation fails | Retry up to 3× with exponential backoff; if `HRC_ZK_PROOF_REQUIRED_FOR_MAINCHAIN=true`, abort |
| Main Chain write fails | Exception logged, `last_proof_submission` not updated — retry on next block |
| Main Chain ZK verification fails | `add_proof()` raises, proof block not appended |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Trigger | `SubChain.auto_submit_proof_if_needed()` | `hierarchical/sub_chain.py` |
| ZK generate | `ZKProver.generate_proof()` | `security/zk_prover.py` |
| Proof metadata | `_generate_default_proof_metadata()` | `hierarchical/sub_chain.py` |
| Anchor on Main | `MainChain.add_proof()` | `hierarchical/main_chain.py` |
| ZK verify | `ZKVerifier.verify_proof()` | `security/verify/zk_verifier.py` |

---

## See Also

- [WF-1: Event Submission](./wf-01-event-submission.md) — triggers this workflow
- [WF-9: System Integrity Validation](./wf-09-integrity-validation.md) — checks proof consistency between Sub-Chain and Main Chain
