---
title: "Base Consensus Interface"
description: "Standard interface (Abstract Base Class) defining consensus rules and enterprise content filtering."
icon: material/puzzle-outline
---

# Base Consensus (`hierachain/consensus/base_consensus.py`)

## Overview

`BaseConsensus` is the abstract base class defining the standard framework for all consensus algorithms in the HieraChain system. It ensures consistency between different protocols (PoA, PoF, BFT) and enforces the core business rules of an enterprise blockchain platform.

---

## Core Responsibilities

<div class="grid cards" markdown>

*   :material-gavel:{ .lg .middle } __Protocol Definition__

    ---

    Defines mandatory methods like `validate_block`, `finalize_block`, and `can_create_block` so upper-layer modules (such as Ordering Service) can interact uniformly.

*   :material-filter-check:{ .lg .middle } __Content Filtering (Enterprise Filtering)__

    ---

    Automatically scans and rejects events containing forbidden cryptocurrency terms (`mining`, `coin`, `token`, `wallet`). This is a critical protection layer to maintain HieraChain's enterprise purpose.

*   :material-shield-link-variant:{ .lg .middle } __Integrity Verification__

    ---

    Integrates hash verification mechanisms, digital signatures, and Zero-Knowledge (ZK) Proof support to ensure block data cannot be altered.

</div>

---

## Abstract API Methods

Every consensus algorithm inheriting from `BaseConsensus` must implement the following methods:

| Method | Description |
| :--- | :--- |
| `validate_block(block, prev_block)` | Validates the new block against the previous block. |
| `finalize_block(block)` | Performs final steps (signing, nonce assignment) before saving the block. |
| `can_create_block(node_id)` | Checks whether the current node has permission to create a block. |
| `get_consensus_info()` | Returns current status and configuration information of the protocol. |

---

## Event Validation Rules

The system enforces strict forbidden keyword filtering:
*   **Checked data**: All fields in `details` and event content.
*   **Excluded fields**: Cryptographic fields such as `signature`, `hash`, `merkle_root`, and `zk_proof` are ignored to avoid false identification of random strings.
*   **Action**: If a violation keyword is detected, `validate_event_for_consensus` returns `False`, causing the block to be rejected.

---

## Zero-Knowledge (ZK) Integration

`BaseConsensus` provides helper functions for ZK proof verification (`_verify_block_zk_proof`). When `settings.ENABLE_ZK_PROOFS` is enabled, every consensus block must carry a valid proof to demonstrate the correctness of state changes without revealing raw data.

---

## Related

*   [Proof of Authority (PoA)](./poa.md)
*   [Proof of Federation (PoF)](./pof.md)
*   [Ordering Service](./ordering.md)
