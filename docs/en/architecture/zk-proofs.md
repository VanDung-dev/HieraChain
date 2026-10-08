---
title: "Zero-Knowledge Proofs"
description: "Explanation of Zero-Knowledge Proofs mechanism in HieraChain, including ZKProver, ZKVerifier, and operating modes."
icon: material/shield-key
---

# Zero-Knowledge Proofs

HieraChain exposes a ZK proof interface for Sub-chain submissions to MainChain. The current implementation supports mock proofs for development; production proving and verification are not implemented.

### 1. How ZKProver & ZKVerifier Work

The system provides two core modules for this task:

* **`ZKProver`** (Located at Sub-chain - `hierachain/security/zk_prover.py`):
  
    * Acts as the Prover.
    * Sub-chain proof inputs use the previous and latest block event Merkle roots.
    * The current mock implementation binds those inputs to a hash. It does not prove an entity projection transition or validate business rules.

* **`ZKVerifier`** (Located at Main-chain - `hierachain/security/verify/zk_verifier.py`):
  
    * Acts as the Verifier.
    * For mock proofs, `ZKVerifier` checks the format and the commitment to the supplied public inputs.
    * A rejected proof prevents its MainChain submission. Mock commitments are forgeable and do not provide a production zero-knowledge guarantee.

### 2. Operating Modes

Zero-Knowledge Proofs in HieraChain support two running modes depending on the actual deployment environment of the Sub-chain (flexibly configured via `ZK_MODE` environment variable):

#### a. Mock Mode (Default)

* This is the Development (Dev) or Testing environment mode.
* Mock mode uses the `mock_zkp_v2\x00` format with a SHA-256 commitment to public inputs; it does not execute a SNARK circuit.
* Instead of running algorithm circuits, mock mode uses interpolated hash computation (`hashlib.sha256`) on Public Inputs parameters and simulates a 100-500ms delay to mimic the real proof system.
* Supports Main/Sub integrated development without requiring significant hardware resources.

#### b. Production Mode (ZoKrates)

* This is a reserved production interface, currently unsupported.
* Requires the proving key directory at `ZK_PROVING_KEY_PATH` and verification key at `ZK_VERIFICATION_KEY_PATH`.
* The current production methods raise `NotImplementedError`; configuring key paths does not enable an external proving service.

### 3. Public Inputs

As defined by `ZKPublicInputs`, the input arguments (synchronized between Prover and Verifier) include:

* **`old_state_root` (str)**: Event Merkle root of the immediately preceding block; the submission path uses `genesis` when no preceding block exists.
* **`new_state_root` (str)**: Event Merkle root of the latest block, with the existing block-hash fallback when needed.
* **`block_index` (int)**: Block sequence number bound into the proof; the submission layer must still enforce freshness and deduplication.
* **`sub_chain_name` (str)**: Full identifier or name of the Sub-chain pushing the Proof.

These parameters are serialized as standardized JSON bytes (using `sort_keys=True`) before being hashed for Proof generation.

`WorldState.get_state_root()` hashes the entity query projection and is a separate diagnostic root. It is not supplied by the current cross-level proof path. Production proving and verification currently raise `NotImplementedError`; this root clarification does not implement a production ZK circuit.
