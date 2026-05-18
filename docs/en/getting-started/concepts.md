---
title: "Core Concepts"
description: "Core concepts of HieraChain: Chain, Block, Event, Proof, Main/Sub-Chain and how they relate."
icon: material/lightbulb
---

# Core Concepts

This page summarizes the foundational concepts for reading and using HieraChain effectively. When encountering new terms, see the [Glossary](../glossary.md).

## Key Concepts

* Chain: A collection of Blocks linked by `previous_hash`. HieraChain has two chain layers: `Main Chain` and domain-specific `Sub-Chains`.
* Block: A group of Events with metadata (header). See `hierachain/core/block.py`.
* Event: A business operation (not a cryptocurrency transaction). Stored as Arrow tables per schema in `hierachain/core/schemas.py`.
* Proof: A cryptographic footprint (e.g. Merkle root/hash) representing Sub-Chain state, anchored to the Main Chain.
* Hierarchy: Architecture where Main Chain supervises multiple Sub-Chains. Managed by `HierarchyManager`.

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

### Data Structure

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
        +hash hash
        +hash previous_hash
        +list events
        +hash merkle_root
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

## Basic Flow

1. Write Event to Sub-Chain → batch into Block by conditions (size/time).
2. Generate Proof from Block (e.g. Merkle root) → submit to Main Chain for anchoring.
3. Trace/Statistics: API allows entity tracking, Block/Chain viewing, and system information aggregation.

## Related Source Files

* Core: `hierachain/core/{block.py, blockchain.py, schemas.py}`
* Hierarchical: `hierachain/hierarchical/{main_chain.py, sub_chain.py, hierarchy_manager.py}`
* API: `hierachain/api/v1/{endpoints.py, schemas.py}`
* Security: `hierachain/security/*`
* Configuration: `hierachain/config/settings.py`

## Related

* Quickstart: [Quickstart](quickstart.md)
* Architecture Overview: [Overview](../architecture/overview.md)
* Glossary: [Glossary](../glossary.md)
