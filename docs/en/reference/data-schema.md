---
title: "Data Schema & Protocol"
description: "Defines data structures (Apache Arrow) and data flow protocols in HieraChain."
icon: material/file-tree
---

# Data Schema & Protocol

This document defines in detail the Data Schema and communication protocols within HieraChain. The system uses **Apache Arrow** as the primary storage and transport format to ensure high performance.

## Core Data Structures

HieraChain strictly adheres to the following Schema definitions to ensure consistency across the entire network (Main Chain & Sub Chains).

### Event

Event is the smallest data unit, representing a specific business action.

**Schema Definition (`hierachain.core.schemas.EVENT_SCHEMA`):**

| Field Name | Type (Arrow) | Description |
|------------|--------------|-------------|
| `entity_id` | `string` | **Metadata Field**. Identifier of the affected entity (e.g., ProductID, OrderID). **Note:** Not used as Block identifier. |
| `event` | `string` | Event type (e.g., `CREATED`, `UPDATED`, `TRANSFERRED`). |
| `timestamp` | `float64` | Time of event occurrence (Unix timestamp). |
| `details` | `map<string, string>` | Additional Key-Value information (On-chain data). |
| `details_cid` | `string` | **IPFS CID**. Reference to large data stored off-chain. |
| `details_nonce` | `string` | **Encryption Nonce**. Decryption key for off-chain data (used for AES-GCM). |
| `data` | `binary` | Main data payload (internal JSON component, includes both on-chain and off-chain refs). |

### Transaction

Transaction is a wrapper containing an Event along with digital signature and zero-knowledge proof.

**Schema Definition (`hierachain.core.schemas.TRANSACTION_SCHEMA`):**

| Field Name | Type (Arrow) | Description |
|------------|--------------|-------------|
| `tx_id` | `string` | Unique transaction identifier (UUID or Hash). |
| `entity_id` | `string` | Synchronized with Event entity_id. |
| `event_type` | `string` | Synchronized with Event event. |
| `arrow_payload` | `binary` | Event data serialized in Arrow format. |
| `signature` | `string` | Digital signature of the transaction creator (Ed25519/ECDSA). |
| `timestamp` | `float64` | Transaction creation time. |
| `zk_proof` | `binary` | (Optional) Zero-Knowledge proof to verify correctness without revealing data. |
| `zk_public_inputs` | `binary` | (Optional) Public inputs accompanying the ZK Proof. |

### Block

Block is a collection of ordered and packaged Events.

**Block Header Schema:**

| Field Name | Type (Arrow) | Description |
|------------|--------------|-------------|
| `index` | `int64` | Block sequence number in the chain (Height). |
| `timestamp` | `float64` | Block creation time. |
| `previous_hash` | `string` | SHA-256 hash of the previous block (creates chain link). |
| `nonce` | `int64` | Random number used in Proof-of-Work (if applicable) or to ensure uniqueness. |
| `merkle_root` | `string` | Root hash of the Merkle tree, representing all Events in the Block. |
| `hash` | `string` | Identifier hash of this Block. |

**Block Body:**

* Contains a list of **Events** (stored as `pyarrow.Table` for optimized access).

## Data Flow Protocol

Data processing flow from Client to Chain storage:

1. **Submission**:

    * Client creates an `Event`.
    * SDK wraps the Event into a `Transaction`, signs it (`signature`), and optionally generates `zk_proof`.
    * Sends `Transaction` to the **Ordering Service**.

2. **Ordering**:

    * **Ordering Service** receives the Transaction, verifies signature and basic validity.
    * Places the Transaction in a queue to ensure consistent ordering.
    * Groups Transactions into a Batch for Block creation.

3. **Consensus & Commit**:

    * Node creates a new Block from the ordered Transaction batch.
    * Computes `Merkle Root` and `Block Hash`.
    * Executes consensus algorithm (PoA/PoF/BFT) to confirm the Block.
    * After consensus, the Block is added to `MainChain` or `SubChain`.
    * `World State` is updated.

## Serialization Standards

* **Apache Arrow**: Used for internal storage and inter-Node transport (Performance).
* **JSON**: Used for Client API (REST) for easy integration with Web/Mobile Apps.
* **Protobuf/gRPC**: (Optional) Used for high-performance internal communication between microservices.
