---
title: "Decentralized Zero-Knowledge Proofs"
description: "Current ZK implementation scope: mock proof-flow fixtures and unsupported production placeholders."
icon: material/brain
---

# Decentralized Zero-Knowledge Proofs

HieraChain exposes prover and verifier interfaces for cross-chain proof flows. The implemented mode is a development mock based on a SHA-256 commitment to public inputs. It does not prove business rules, state-transition correctness, or zero-knowledge privacy. Production proving and verification are not implemented.

## 1. ZK Prover

**File**: `hierachain/security/zk_prover.py`

* `ZKProver(mode="mock")` generates a fixture containing a hash of public inputs and random padding. Anyone with the inputs can construct a matching commitment.
* `ZKProver(mode="production").generate_proof(...)` returns `ZKProofResult(success=False, proof=b"", error=...)` because the production backend is unimplemented.
* `generate_proof_bytes(...)` raises `ZKProvingError` when generation fails. Loading a proving key or setting a circuit path does not implement the backend.

## 2. ZK Verifier

**File**: `hierachain/security/verify/zk_verifier.py`

* Mock verification compares the commitment with a hash of the public inputs. A matching hash establishes no mathematical proof of a valid transition.
* For well-formed inputs, production verification raises `ZKVerificationError` wrapping the unimplemented backend error. Current checks return `False` for malformed values they recognize, but wrong-typed roots or block indices can raise before backend dispatch.
* Loading a verification key does not make production verification available.

## 3. Configuration and runtime boundary

`HRC_ENABLE_ZK_PROOFS` defaults to `false`; `HRC_ZK_MODE` defaults to `mock`. Enabling verification does not install a production backend. Keep mock mode confined to development and test proof flows. Setting `HRC_ZK_MODE=production` alone cannot provide a functioning ZK deployment.

Signed block verification, Merkle roots and durable MainChain anchors are separate implemented integrity mechanisms. They must not be described as zero-knowledge proofs of business correctness. Applications needing real ZK validation require a separately implemented and validated proving/verifying backend and circuit contract.

## Related

* [Hierarchical architecture and feature support](../modules/hierarchical.md)
* [Authorization & Access Control](./authorization-access-control.md)
