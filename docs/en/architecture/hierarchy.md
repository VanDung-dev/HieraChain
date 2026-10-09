---
title: "Hierarchical Architecture (Detailed)"
description: "Main Chain/Sub-Chain/HierarchyManager relationships, channels/multi-org, private data, cross-chain transactions, proof anchoring, and rebalancing."
icon: material/sitemap
---

# Hierarchical architecture

## Purpose

This page explains how HieraChain organizes its hierarchy. It covers how Sub-Chains interact with the Main Chain through `HierarchyManager`, how channels and the multi-org model work, how private data is handled, how cross-chain transactions use 2PC, how proofs are anchored, and how Sub-Chains are rebalanced.

## Components and concepts

* Main Chain: `hierachain/hierarchical/main_chain/base.py` stores proofs from Sub-Chains and aggregates integrity reports.
* Sub-Chain (Domain Chain): `hierachain/hierarchical/sub_chain/base.py` processes domain events, orders and closes blocks, and generates proofs.
* Hierarchy Manager: `hierachain/hierarchical/hierarchy_manager/base.py` coordinates the chain system, manages Sub-Chain lifecycle, cross-chain transactions and system statistics.
* Channel: `hierachain/hierarchical/channel/channel.py` provides a private communication space for groups of organizations and holds channel creation policies.
* Multi-Org: `hierachain/hierarchical/multi_org.py` handles organization initialization, the multi-org network, and the relationship between channels and organizations.
* Private Data: `hierachain/hierarchical/private_data.py` provides collection objects and access checks with in-memory library storage. The manager does not persist these collections, and the REST private-data write route returns HTTP 501.
* Cross-Chain Transaction Manager: `hierachain/hierarchical/transaction_manager.py` coordinates 2PC transactions between Sub-Chains.

### Typical flow

```mermaid
graph TD
    User[Client/User] -->|Submit Event| SubChain
    SubChain -->|1. Ordering| Orderer[Ordering Service]
    Orderer -->|2. Finalize| Consensus[Consensus Layer]
    Consensus -->|Finalized block| Orderer
    Orderer -->|3. Sign and persist| Blocks[Block Storage]
    Blocks -->|4. Queue and apply unchanged block| SubChain
    SubChain -->|5. Submit Proof| MainChain[Main Chain]
    MainChain -->|6. Persist Proof Anchor| Storage[Proof Storage]
    SubChain -->|Apply Finalized Events| Projection[WorldState Projection]
```

1. Create a Sub-Chain with `HierarchyManager.create_sub_chain(name, domain_type, metadata)`. This initializes a DomainChain and connects it to the Main Chain.
2. Submit an event with `SubChain.add_event()`. It acknowledges journal/queue acceptance; ordering later finalizes, signs and persists a block before the consumer applies it.
3. Anchor the proof to the Main Chain with `SubChain.submit_proof_to_main(main_chain, ...)` or `HierarchyManager.submit_proof_to_main_chain(name)`.
4. Run cross-chain transactions (2PC) with `HierarchyManager.transaction_manager.initiate_transaction(src, dst, payload)`, which handles prepare, commit and rollback.
5. Channels: create a channel between organizations. Private-data collection objects need application-managed persistence; REST private-data writes are unimplemented (HTTP 501).

## Related configuration (settings.py, actual `HRC_*`)

* Consensus/Ordering: see [Consensus & Ordering](consensus.md) and `HRC_CONSENSUS_TYPE`/`HRC_MAINCHAIN_CONSENSUS`, `VALIDATOR_TIMEOUT`, `HRC_BLOCK_INTERVAL`.

## Features and limitations

* Features: domain data separation, signed proof anchoring, durable 2PC journal decisions, and channel/multi-org registries on supported storage backends.
* Limitations: direct Python channel/private-data calls require a trusted caller; private-data storage is not supplied by the REST API. 2PC journal acknowledgement is separate from asynchronous block commitment. See [Hierarchical module](../modules/hierarchical.md).

## Related

* Overview: [Overview](overview.md)
* Consensus & Ordering: [Consensus & Ordering](consensus.md)
* Hierarchical module: [Hierarchical](../modules/hierarchical.md)
* Config: [Config](../reference/config.md)
