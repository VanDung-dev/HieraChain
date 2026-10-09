---
title: "Consensus & Ordering"
description: "Overview of PoA/PoF/BFT and Ordering Service in HieraChain; configuration, flow, and invariants."
icon: material/sync
---

# Consensus and ordering

## Purpose

This page describes the consensus mechanisms and the Ordering Service that HieraChain uses to keep blocks and events ordered, intact and verifiable.

## Architecture and concepts

* Base Consensus: `hierachain/consensus/base_consensus.py` defines the base interface for PoA and PoF; BFT uses a separate API.
* Proof of Authority (PoA): `hierachain/consensus/proof_of_authority.py` provides intra-organization consensus with a single MainChain that manages internal domain Sub-Chains.
* Proof of Federation (PoF): `hierachain/consensus/proof_of_federation.py` implements federation membership, rotating leader validation and a leader signature for consortium integration; ordinary block validation does not collect multi-party quorum votes.
* BFT Consensus: `hierachain/consensus/bft/` contains a separate implementation. The runtime paths for MainChain and SubChain use PoA or PoF.
* Ordering Service: `hierachain/consensus/ordering/` orders events before block creation and is built from several components (Processor, Certifier, BlockBuilder).

### Typical flow

```mermaid
sequenceDiagram
    participant SC as Sub-Chain
    participant OS as Ordering Service
    participant C as Consensus (PoA/PoF)
    participant MC as Main Chain

    SC->>OS: 1. Submit Event
    OS->>OS: Queue & Batch
    OS->>OS: 2. Build block and assign index/link
    OS->>C: Finalize block
    C-->>OS: Finalized block
    OS->>OS: Sign header, persist and enqueue
    SC->>OS: get_next_block()
    OS-->>SC: Persisted block
    SC->>SC: 3. Validate/add unchanged block and update state
    SC->>MC: 4. Submit proof (Sub-Chain block hash)
    MC-->>SC: Acknowledge
```

1. A Sub-Chain receives an event and pushes it to the Ordering Service queue.
2. The Ordering Service batches events by size and time thresholds, creates a block, runs its configured consensus finalizer, signs the header and persists the block before queueing it.
3. The Sub-Chain consumer validates and applies the persisted block without changing its index, hash or signature. Sub-Chain consensus is PoA by default or PoF when configured.
4. If Main Chain anchoring is enabled, the Sub-Chain sends a proof containing the latest Sub-Chain block hash to the Main Chain for recording.

## Configuration

Variables in `hierachain/config/settings.py`:

* `CONSENSUS_TYPE`: `proof_of_authority` (default) or `proof_of_federation`.
* `BFT_ENABLED`: the `Settings` class defines this attribute, but it does not select consensus for MainChain or SubChain. It is not an environment variable.
* `VALIDATOR_TIMEOUT`: declared validator timeout exposed by the settings helper; it does not configure the BFT view-change timer.
* `CONSENSUS_FEDERATION_CONFIG`: declared federation defaults; current MainChain/SubChain constructors do not apply this dictionary to PoF. Configure the actual consensus instance consistently across nodes.

Environment example:

```dotenv
HRC_CONSENSUS_TYPE=proof_of_authority
HRC_ZK_REQUIRED_MAINCHAIN=false
```

## Features and limitations

* PoA trusts registered authorities. Throughput depends on batching, journal synchronization and storage.
* PoF balances trust and distribution, but it requires federation membership to be managed.
* The BFT implementation lives under `hierachain/consensus/bft/` and is separate from the MainChain and SubChain runtime paths.
* Ordering keeps event order and batching stable before a block is finalized.

## Related

* Architecture Overview: [Overview](overview.md)
* Hierarchical module: [Hierarchical](../modules/hierarchical.md)
* Data Models: [Data Models](../reference/data-models.md)
* Config: [Config](../reference/config.md)
