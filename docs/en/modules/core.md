---
title: "Core Module"
description: "Core ledger primitives: Block, Blockchain, Merkle Tree, and Multi-tier Caching."
icon: material/cube
---

# Core Module (`hierachain/core/*`)

## 1. Overview

The `core` module contains foundational data structures for the ledger. Blocks store events in Apache Arrow tables for fast in-memory filtering and deterministic hashing. Cryptographic Merkle trees prove event inclusion, and a multi-level cache speeds up block, event, and entity lookups.

## 2. Foundational components

All core primitives reside in `hierachain/core/`.

### 2.1 Block (`block.py`)

* Stores event records in a `pyarrow.Table`.
* Queries event fields with Arrow compute expressions rather than Python loops.
* Calculates deterministic block hashes and Merkle roots.

### 2.2 Blockchain (`blockchain.py`)

* Coordinates chain state, genesis initialization, and pending event queues.
* Implements thread-safe locking with deadlock detection.
* Maintains entity indexes for fast historical event lookups.

### 2.3 Merkle tree (`merkle_tree.py`)

* Constructs binary Merkle trees from event hashes.
* Produces cryptographic inclusion proofs for audit verification.
* Validates Merkle roots across hierarchical chain tiers.

### 2.4 Cache (`cache.py`)

* Provides an in-memory cache with LRU, LFU, FIFO, and TTL eviction policies.
* `KeyManager` uses it for key and permission lookups.

## 3. Block memory and storage layout

Each `Block` encapsulates an Arrow table with structured metadata:

1. Compact binary layout reduces Python object overhead.
2. Filter queries on `entity_id` and `event` execute through native Arrow kernels.
3. Serialized binary payloads ensure stable hashing across platforms.

```python
# Query events by entity on a Block instance
entity_events = block.get_events_by_entity("PROD-123")
```

## 4. Blockchain thread safety and locking

The `Blockchain` class coordinates concurrent access through a timeout-guarded lock:

* Monitors lock acquisition duration with a configurable threshold.
* `safe_lock(timeout)` prevents thread hangs under heavy concurrent writes.
* Callback hooks report contention warnings to the monitoring layer.

## 5. Concurrent execution

Cryptographic verification tasks and cross-chain synchronization run concurrently via `ThreadPoolExecutor` workers managed by the runtime environment. Hashing and signature checks scale across CPU cores while preserving sequential block order.

## Related

* [Hierarchical Architecture](../architecture/hierarchy.md)
* [Storage Module](./storage.md)
* [Security Overview](./security.md)
