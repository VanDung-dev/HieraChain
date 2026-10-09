---
title: "Data Schema & Protocol"
description: "Defines data structures (Apache Arrow) and data flow protocols in HieraChain."
icon: material/file-tree
---

# Data schema and protocol

HieraChain uses JSON for REST requests and Apache Arrow tables for block event storage. The canonical binary event payload preserves typed details; the Arrow metadata columns support filtering and indexing. See [Data Models](./data-models.md) for serialization and hash contracts.

## Event

The Arrow `EVENT_SCHEMA` is defined in `hierachain/core/block.py`.

| Field | Arrow type | Description |
|:------|:-----------|:------------|
| `entity_id` | `string` | Business entity identifier |
| `event` | `string` | Internal event type |
| `timestamp` | `float64` | Unix timestamp |
| `details` | `map<string, string>` | String projection of detail values for Arrow metadata |
| `details_cid` | `string` | Optional off-chain IPFS reference |
| `details_nonce` | `string` | Public AES-GCM nonce for an encrypted off-chain object |
| `data` | `binary` | Canonical JSON event payload preserving JSON fields and typed details; top-level byte fields are omitted |

`details_nonce` is not a decryption key. Encrypted IPFS retrieval also requires the stable encryption key and any metadata supplied as AAD. See [IPFS Storage](../workflows/ipfs-storage.md).

### REST input

`EventRequest` in `hierachain/api/ledger/schemas.py` requires `entity_id` and `event_type`. Optional fields are `details`, `details_cid`, `details_nonce`, `details_metadata`, `sender` and `signature`. It has no `timestamp` field. The Ledger API maps `event_type` to the internal `event` field and assigns the current server time.

The seven-column Arrow schema has no dedicated columns for `signature`, `zk_proof` or `zk_public_inputs`. Additional JSON fields can still be stored in canonical event bytes; their presence alone does not establish cryptographic verification.

The HTTP SDK sends the caller's event data to the Ledger API as JSON. It does not wrap it in a separate signed object or generate a ZK proof. MainChain proof submissions and signed block headers have separate validation contracts.

## Block

`Block.events` is a `pyarrow.Table`. Block serialization includes these header fields:

| Field | Meaning |
|:------|:--------|
| `index` | Block position in the chain |
| `timestamp` | Block creation timestamp |
| `previous_hash` | Previous block hash |
| `nonce` | Header field included in serialization and hashing; PoA/PoF do not use it for work-based consensus |
| `merkle_root` | Root derived from the block's events |
| `hash` | Calculated block hash |
| `creator_id` | Node identity of the block signer |
| `signature` | Ed25519 signature of the canonical block header |

Header fields are not an additional Arrow event schema. Verifiers use the operator-approved creator-to-public-key map to validate signatures.

## Submission and commitment

1. The Ledger API validates JSON input and calls `SubChain.add_event()`.
2. The ordering service journals and queues the event. The returned event ID confirms acceptance; commitment follows asynchronously.
3. The background processor certifies events and batches them. The block manager assigns the block index and link, runs consensus finalization, signs the header and persists the block before queueing it for the Sub-Chain consumer.
4. The consumer validates and applies the persisted block unchanged, updates WorldState, and checks whether proof submission is due.

See [Event Submission](../workflows/event-submission.md) for failure handling. BFT is a separate library implementation; MainChain/SubChain runtime selection uses PoA or PoF.

## Serialization and transport

REST uses JSON. Internal event tables and the event journal use Arrow representations with canonical event bytes for integrity checks. Network messaging is implemented under `hierachain/network/`; the package does not provide a Protobuf/gRPC transport. Do not infer a transport protocol from the event table format.
