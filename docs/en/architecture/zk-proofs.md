---
title: "Zero-Knowledge Proofs"
description: "Explanation of Zero-Knowledge Proofs mechanism in HieraChain, including ZKProver, ZKVerifier, and operating modes."
icon: material/shield-key
---

# Zero-Knowledge Proofs

HieraChain uses **Zero-Knowledge Proofs (ZK)** to ensure transaction authenticity across the hierarchical system without revealing detailed data of each Event. Sub-chains generate Proofs demonstrating valid state transitions, and the Main-chain verifies those Proofs.

### 1. How ZKProver & ZKVerifier Work

The system provides two core modules for this task:

* **`ZKProver`** (Located at Sub-chain - `hierachain/security/zk_prover.py`):
  
    * Acts as the Prover.
    * When a Sub-chain generates a new block, it creates a new state (World State).
    * `ZKProver` generates Proof code segments to prove the state transition logic from `old_state_root` to `new_state_root` at the corresponding `block_index`.

* **`ZKVerifier`** (Located at Main-chain - `hierachain/security/verify/zk_verifier.py`):
  
    * Acts as the Verifier.
    * Upon receiving Proof signals from Sub-chain, `ZKVerifier` analyzes and verifies mathematical validity and state integrity.
    * Completely resolves **Fake Proofs** risk. If a Proof fails verification, the attached transaction on Main-chain will be outright rejected.

### 2. Operating Modes

Zero-Knowledge Proofs in HieraChain support two running modes depending on the actual deployment environment of the Sub-chain (flexibly configured via `ZK_MODE` environment variable):

#### a. Mock Mode (Default)

* This is the Development (Dev) or Testing environment mode.
* Mock Mode simulates Groth16/Plonk ZK-SNARK by generating a simulated proof format of 2KB - 4KB with `mock_zkp_v2\x00`.
* Instead of running algorithm circuits, mock mode uses interpolated hash computation (`hashlib.sha256`) on Public Inputs parameters and simulates a 100-500ms delay to mimic the real proof system.
* Supports Main/Sub integrated development without requiring significant hardware resources.

#### b. Production Mode (ZoKrates)

* This is the actual production operation mode for Mainnet/Enterprise environments.
* Requires the proving key directory at `ZK_PROVING_KEY_PATH` and verification key at `ZK_VERIFICATION_KEY_PATH`.
* Proofs are generated via an External Service (like ZoKrates) containing high-order SNARK mathematical equations that are extremely secure and hard to forge.

### 3. Public Inputs

As defined by `ZKPublicInputs`, the input arguments (synchronized between Prover and Verifier) include:

* **`old_state_root` (str)**: Merkle Root of the World State at the immediately preceding block. Must be a valid hash.
* **`new_state_root` (str)**: Latest Merkle Root after events are incorporated into the current update block.
* **`block_index` (int)**: Block sequence number (this mechanism completely prevents Replay attacks).
* **`sub_chain_name` (str)**: Full identifier or name of the Sub-chain pushing the Proof.

These parameters are serialized as standardized JSON bytes (using `sort_keys=True`) before being hashed for Proof generation.
