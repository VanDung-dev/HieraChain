---
title: "Core Concepts"
description: "Core concepts of HieraChain: Chain, Block, Event, Proof, Main/Sub-Chain and how they relate."
icon: material/lightbulb
---

# Core concepts

These concepts describe the ledger's data and hierarchy. See the [Glossary](../glossary.md) for other terms.

## Key concepts

* Chain: A sequence of blocks linked by `previous_hash`. HieraChain has a `Main Chain` and domain-specific `Sub-Chains`.
* Block: A group of events stored in an Arrow table, with a header containing the block index, timestamp, previous hash, nonce, Merkle root and creator identity. See `hierachain/core/block.py`.
* Event: A business record with `entity_id`, `event` and `timestamp`. Details can describe the operation. `EVENT_SCHEMA` in `hierachain/core/block.py` defines storage columns; canonical event bytes preserve JSON fields and typed details.
* Proof: An anchor containing a Sub-Chain block hash and summary metadata, including its Merkle root. A ZK proof can be included under the configured proof policy. This anchor is distinct from an individual event inclusion proof.
* Hierarchy: The MainChain and registered SubChains coordinated by `HierarchyManager`.

```mermaid
graph TD
    Main[Main Chain]
    subgraph Domains
        A[Sub-Chain A]
        B[Sub-Chain B]
        C[Sub-Chain C]
    end
    Main --> A
    Main --> B
    Main --> C

    note[Main Chain stores Proofs <br/> Sub-Chain stores detailed Events]
    Main -.- note
```

### Data structure

The diagram shows runtime classes and a conceptual event record. `Block.events` is a `pyarrow.Table`; exported event snapshots are lists of dictionaries.

```mermaid
classDiagram
    direction LR
    class HierarchyManager {
        +MainChain main_chain
        +dict sub_chains
        +create_sub_chain()
        +start_operation()
    }
    class Blockchain {
        +list chain
        +add_block()
        +get_latest_block()
    }
    class Block {
        +int index
        +string hash
        +string previous_hash
        +pyarrow.Table events
        +string merkle_root
    }
    class Event {
        +string entity_id
        +string event
        +float timestamp
        +dict details
    }

    HierarchyManager "1" *-- "1" Blockchain : main_chain
    HierarchyManager "1" *-- "many" Blockchain : sub_chains
    Blockchain "1" *-- "many" Block
    Block "1" *-- "many" Event
```

## Basic flow

1. Submit an event to a Sub-Chain. The event ID confirms acceptance into ordering; size and time settings determine when events are batched into a block.
2. Ordering finalizes, signs and persists the block. The Sub-Chain consumer validates and applies it. Proof submission anchors a finalized block hash and summary metadata to the MainChain according to the proof schedule or an explicit request.
3. Query committed events by entity or inspect blocks and chain statistics through the API.

## Related source files

* Core: `hierachain/core/block.py`, `hierachain/core/blockchain.py`
* Hierarchical: `hierachain/hierarchical/main_chain/base.py`, `hierachain/hierarchical/sub_chain/base.py`, `hierachain/hierarchical/hierarchy_manager/base.py`
* API: `hierachain/api/ledger/router.py`, `hierachain/api/ledger/schemas.py`
* Security: `hierachain/security/*`
* Configuration: `hierachain/config/settings.py`

## Related

* Quickstart: [Quickstart](quickstart.md)
* Architecture Overview: [Overview](../architecture/overview.md)
* Glossary: [Glossary](../glossary.md)
