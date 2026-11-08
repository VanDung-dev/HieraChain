---
title: "Network Module"
description: "ZeroMQ transport and peer lifecycle for HieraChain nodes."
icon: material/access-point-network
---

# Network Module (`hierachain/network/*`)

## Overview

The **Network** module handles communication between HieraChain nodes over **ZeroMQ**. `ZmqNode` owns the sockets, replay protection and framing limits; `NetworkClient` adds seed registration, peer lifecycle and status reporting. The API server creates `NetworkClient` directly.

---

## Core Components

### 1. ZMQ Transport (`zmq_transport.py`)
Implements the asynchronous P2P model using **ROUTER** (for receiving) and **DEALER** (for sending) sockets.

*   **Transport**: Uses asynchronous sockets; broadcasts send to registered peers sequentially.
*   **Identity Management**: Manages node identities at the socket level for accurate routing.
*   **Replay buffer**: Retains at most 1,000 timestamp/nonce pairs with nonce strings of at most 128 characters. When all entries are still within the 60-second window, new messages are rejected until an entry expires.

ZeroMQ accepts frames up to 1 MiB and exactly two application frames (sender identity and body); excess frames are drained without accumulating a Python multipart list. Plain transport requires configured peer IDs and isolates replay caches per peer; it provides no cryptographic identity guarantee. These limits do not replace upstream connection and bandwidth controls.

### 2. Network Client (`network_client.py`)

`NetworkClient` tracks seed and manually registered peers in the same registry. Removing a peer also closes its outbound DEALER socket. A peer is initially healthy for 60 seconds after registration; each accepted inbound message from its registered socket identity renews that period. An idle peer becomes unhealthy when status or peers are read. This health indicator does not authenticate the peer or confirm delivery of outbound messages.

If `ZmqNode.start()` fails, it closes the transport sockets and context before raising `NetworkError`. `NetworkClient.start()` releases a partially initialized transport and returns `False`; after resolving the cause, calling `start()` again creates a fresh transport. `NetworkClient.stop()` also cleans up a transport that never reached the running state and can be called repeatedly.

---

## P2P Configuration (Environment Variables)

| Environment Variable | Function | Recommended Value (Prod) |
| :--- | :--- | :--- |
| `HRC_P2P_ENABLED` | Enable the P2P network layer | `true` when peers are used |
| `HRC_P2P_HOST` / `HRC_P2P_PORT` | Local bind address | Deployment-specific |
| `HRC_PEERS` | Comma-separated seed nodes (`node_id@ip:port`) | Known peer list |

---

## Related

*   [Security](./security.md)
*   [Configuration](./config.md)
