---
title: "Cluster Module"
description: "Cross-level synchronization and cluster message data types."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Overview

The **Cluster** module contains the cross-level synchronization runtime and the data types used by cluster messages.

---

## Architecture & Main Components

The package currently exposes two small building blocks:

<div class="grid cards" markdown>

*   :material-connection:{ .lg .middle } __Cross-Level Sync__

    ---

    __File__: `cross_level_sync.py`

    * Synchronization of proofs between Main Chain and Sub-Chains.
    * Ensures integrity of the enterprise hierarchy tree.

*   :material-shield-lock:{ .lg .middle } __Lockdown Message Types__

    ---

    __File__: `lockdown_types.py`

    * Defines serializable lockdown and quarantine messages.
    * Provides HMAC signing and verification helpers.

</div>

---

## Usage

`HierarchyManager` owns the optional `CrossLevelSyncManager` instance and uses it
to synchronize proof metadata between the main chain and sub-chains. The message
types in `lockdown_types.py` are data and signing helpers; they do not implement
a cluster-wide voting or lockdown coordinator.

---

## Related

*   [P2P Networking](./network.md)
*   [Security Identity](./security.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)
