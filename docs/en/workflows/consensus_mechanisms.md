---
title: "Consensus Mechanisms"
description: "Comparison and technical specifications of PoA, PoF, and BFT consensus mechanisms in HieraChain."
icon: material/sync
---

# Consensus Mechanisms Reference

**Related workflows**: [Event Submission](./event-submission.md) · [BFT Consensus](./bft-consensus.md)

HieraChain supports three pluggable consensus mechanisms, configured via the `HRC_CONSENSUS_TYPE` environment variable. The event submission flow (Event Submission) is identical regardless of which mechanism is selected — only the `finalize_block()` step differs.

---

## Mechanism Comparison

| Aspect | PoA | PoF | BFT |
|:-------|:----|:----|:----|
| **Config value** | `proof_of_authority` | `proof_of_federation` | `byzantine_fault_tolerant` |
| **Who finalizes** | Any registered authority | Only rotating leader: `Validators[index % n]` | 2f+1 of n validators via PBFT |
| **Signature type** | Ed25519 (asymmetric) | SHA-256 federation signature | Aggregated PBFT votes |
| **Leader rotation** | Optional round-robin | Enforced — deterministic by block index | View-based, changes on failure |
| **ZK Proof check** | Optional | Enforced in `validate_block()` | N/A |
| **Min validators** | 1 authority sufficient | ≥ 3 (`min_validators` config) | n ≥ 3f + 1 |
| **Fault model** | Trust the authority identity | Distributed trust, tolerate absent validator | Tolerates up to f Byzantine nodes |
| **Use case** | Private / internal networks | Consortium / multi-org | Critical / adversarial environments |

---

## Proof of Authority (PoA)

> Activated when `HRC_CONSENSUS_TYPE=proof_of_authority` (default).
> A single pre-registered authority signs the block with its Ed25519 private key.

```mermaid
sequenceDiagram
    autonumber
    participant OS as ⚙️ OrderingService
    participant POA as 🔏 ProofOfAuthority

    OS->>POA: finalize_block(block, authority_id)
    POA->>POA: is_authority(authority_id)
    Note right of POA: Reject if not in authority registry
    POA->>POA: _check_block_timing(block, previous_block)
    Note right of POA: block.timestamp - prev.timestamp >= block_interval / 2
    POA->>POA: _validate_block_events()
    Note right of POA: Scan all events for forbidden crypto terms
    POA->>POA: _create_authority_signature(block, authority_id, private_key)
    Note right of POA: Ed25519 sign(hash + authority_id + timestamp)<br/>Fallback to random KeyPair in test mode
    POA->>POA: Append consensus_finalization event<br/>{ authority_id, authority_signature, finalized_at }
    POA-->>OS: Finalized Block ✅
```

### Key Classes — PoA

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Authority check | `ProofOfAuthority.is_authority()` | `consensus/proof_of_authority.py` |
| Timing check | `_check_block_timing()` | `consensus/proof_of_authority.py` |
| Sign block | `_create_authority_signature()` | `consensus/proof_of_authority.py` |
| Finalize | `ProofOfAuthority.finalize_block()` | `consensus/proof_of_authority.py` |

---

## Proof of Federation (PoF)

> Activated when `HRC_CONSENSUS_TYPE=proof_of_federation`.
> Leader is elected deterministically by block index. ZK proof is enforced.

```mermaid
sequenceDiagram
    autonumber
    participant OS as ⚙️ OrderingService
    participant POF as 🤝 ProofOfFederation

    OS->>POF: finalize_block(block, authority_id)
    POF->>POF: can_create_block(authority_id)
    Note right of POF: Requires >= min_validators (default 3)
    POF->>POF: get_current_leader(block.index)<br/>= Validators[ block.index % n ]
    POF->>POF: validate_block_proposer(block.index, authority_id)
    Note right of POF: Reject if authority_id != expected leader
    POF->>POF: _validate_block_events()
    Note right of POF: Scan all events for forbidden crypto terms
    POF->>POF: _verify_block_zk_proof(block, previous_block)
    Note right of POF: Enforced — fails block if ZK invalid
    POF->>POF: _create_federation_signature(block, leader_id)<br/>SHA-256(hash:leader_id:block.index:time)
    POF->>POF: Append consensus_finalization event<br/>{ leader_id, validators_count, round, signature }
    POF-->>OS: Finalized Block ✅
```

### Key Classes — PoF

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Leader election | `ProofOfFederation.get_current_leader()` | `consensus/proof_of_federation.py` |
| Proposer check | `validate_block_proposer()` | `consensus/proof_of_federation.py` |
| ZK verify | `_verify_block_zk_proof()` | `consensus/proof_of_federation.py` |
| Federation sign | `_create_federation_signature()` | `consensus/proof_of_federation.py` |
| Finalize | `ProofOfFederation.finalize_block()` | `consensus/proof_of_federation.py` |

---

## Byzantine Fault Tolerance (BFT / PBFT)

> Activated when `HRC_CONSENSUS_TYPE=byzantine_fault_tolerant`.
> Full 3-phase PBFT. See [BFT Consensus](./bft-consensus.md) for the complete flow.

**Requirements**: n ≥ 3f + 1 nodes to tolerate f faulty nodes.

**View Change**: If the leader fails within timeout, `view += 1`, new leader = `Validators[view % n]`, protocol restarts from Phase 1.

---

## Configuration Reference

| Variable | Values | Description |
|:---------|:-------|:------------|
| `HRC_CONSENSUS_TYPE` | `proof_of_authority` (default), `proof_of_federation`, `byzantine_fault_tolerant` | Active consensus mechanism |
| `HRC_ENABLE_ZK_PROOFS` | `true` / `false` | Toggle ZK verification (required for PoF production) |
| `HRC_ZK_MODE` | `mock`, `production` | ZK implementation: SHA-256 simulation or ZoKrates circuits |
