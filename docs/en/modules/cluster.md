---
title: "Cluster Module"
description: "Node cluster management, distributed state synchronization mechanism, and secure lockdown protocol."
icon: material/server-network
---

# Cluster Module (`hierachain/cluster/*`)

## Overview

The **Cluster** module is the brain that coordinates nodes in the HieraChain network. It ensures the system operates as a unified entity, maintains data consistency across hierarchical layers, and provides emergency protection mechanisms when anomalies are detected.

---

## Architecture & Main Components

The system is designed according to a decentralized model with specialized components:

<div class="grid cards" markdown>

*   :material-server-network:{ .lg .middle } __Cluster Manager__

    ---

    __File__: `cluster_manager.py`

    * Health tracking for all nodes.
    * Heartbeat mechanism to detect offline nodes.
    * Quorum voting management (2/3 majority).

*   :material-shield-lock:{ .lg .middle } __Lockdown Protocol__

    ---

    __File__: `lockdown_protocol.py`

    * Gossip protocol over P2P (ZMQ).
    * Secured with HMAC-SHA256 signatures (`HRC_CLUSTER_SECRET`).
    * Quarantine Report mechanism.

*   :material-database-sync:{ .lg .middle } __State Sync (Resurrection)__

    ---

    __File__: `state_sync_manager.py`

    * State recovery after incidents or lockdown.
    * Block gap-fill mechanism.
    * Verification of blocks received from peers.

*   :material-connection:{ .lg .middle } __Cross-Level Sync__

    ---

    __File__: `cross_level_sync.py`

    * Synchronization of proofs between Main Chain and Sub-Chains.
    * Ensures integrity of the enterprise hierarchy tree.

</div>

---

## Lockdown & Recovery Protocol

This is HieraChain's ultimate security mechanism to protect the ledger during attacks or critical system failures.

### 1. Quorum Voting
The system requires an absolute majority (**2/3 of nodes**) to change cluster state:
*   **Lockdown**: Pause all new write operations to protect existing data.
*   **Recovery**: Restart the system after incident resolution.

### 2. Quarantine Report
Before a node performs lockdown and clears its memory buffer (event pool), it broadcasts a `QuarantineReport` containing fingerprints of uncommitted events. This helps other nodes reconcile and detect data gaps after recovery.

### 3. Message Security
All cluster messages (Lockdown, Vote, Sync) must be signed with **HMAC-SHA256** using the shared secret key `HRC_CLUSTER_SECRET`. Invalid or expired messages (>300s) are immediately discarded.

---

## State Synchronization Mechanism

When a new node joins or a node recovers from lockdown, it performs the **Resurrection** process:

1.  **Gap Identification**: Compare the last block index with peers.
2.  **Sync Request**: Send a gap-fill request to healthy nodes.
3.  **Multi-layer Verification**: Each received block is checked for hash chaining and signatures by `BlockVerifier`.
4.  **Merging**: Only valid data is written to the local database.

---

## Configuration & Usage Example

### Environment Variable Configuration
```bash
HRC_CLUSTER_SECRET="your-super-secret-hmac-key"
HRC_QUORUM_THRESHOLD=0.66  # Equivalent to 2/3
```

### Using ClusterManager in Code
```python
from hierachain.cluster.cluster_manager import ClusterManager

manager = ClusterManager(node_id="node-01")

# Register a peer node
manager.register_node("node-02", "192.168.1.10:5000", auth_token="...")

# Vote for lockdown when risk is detected
if manager.vote_lockdown("node-01", reason="Hash tampering detected"):
    print("Quorum reached - System transitioning to LOCKDOWN state")
```

---

## Cluster Health Metrics

`ClusterManager` provides a `ClusterHealthMetrics` object for monitoring:

*   `total_nodes`: Total number of nodes in configuration.
*   `healthy_nodes`: Number of nodes actively sending heartbeats.
*   `is_in_lockdown`: Current lockdown status of the entire cluster.
*   `lockdown_votes`: Current number of lockdown votes.

---

## Related

*   [P2P Networking](./network.md)
*   [Security Identity](./security.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)
