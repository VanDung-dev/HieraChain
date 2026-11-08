---
title: "Cluster Module"
description: "Cross-level synchronization between the main chain and sub-chains."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Overview

The **Cluster** module contains the cross-level synchronization runtime used to anchor Sub-Chain proofs on the MainChain.

---

## Architecture & Main Components

<div class="grid cards" markdown>

*   :material-connection:{ .lg .middle } __Cross-Level Sync__

    ---

    __File__: `cross_level_sync.py`

    * Synchronization of proofs between Main Chain and Sub-Chains.
    * Ensures integrity of the enterprise hierarchy tree.

</div>

---

## Usage

`HierarchyManager` owns the optional `CrossLevelSyncManager` instance and uses it
to synchronize proof metadata between the main chain and sub-chains.

Proof submission for a Sub-Chain is serialized on that chain while it captures
the current tip, checks for an existing anchor, records the MainChain event,
and verifies durable read-back. Concurrent requests for the same Sub-Chain tip
therefore reuse one proof anchor instead of appending duplicates. This lock is
local to one Sub-Chain object; it is not a distributed lock between processes.

---

## Related

*   [Network](./network.md)
*   [Security](./security.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)

## Concurrent status

`CrossLevelSyncManager.get_status()` remains active while any overlapping sync or conflict resolution runs. When the group finishes, it reports `failed` if any operation failed, otherwise `complete`. A later independent operation starts a new group. `get_stats()` includes `active_operations`; `reset()` raises `RuntimeError` while work is active. Completion callback errors are logged and do not reverse an already committed proof.
