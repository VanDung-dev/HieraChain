---
title: "Core Module"
description: "HieraChain's foundational architecture: Block, Blockchain, Apache Arrow, Caching and Parallel Processing."
icon: material/cube
---

# Core Module (`hierachain/core/*`)

## Overview

The **Core** module is the heart of the HieraChain Ledger, providing the highest-performance data structures and processing tools. Here, **Apache Arrow** technology is deeply integrated to manage millions of events at extreme speed, combined with a multi-tier Caching system and Parallel Engine to ensure enterprise-level scalability.

---

## Foundational Components

<div class="grid cards" markdown>

*   :material-database-import:{ .lg .middle } __Block & Apache Arrow__

    ---

    __File__: `block.py`

    * Stores events in columnar storage model.
    * Filters data using Arrow Compute (10-50x faster than Python lists).
    * Deterministic hashing and Merkle Root.

*   :material-link-variant:{ .lg .middle } __Blockchain & Safety__

    ---

    __File__: `blockchain.py`

    * Manages the chain, genesis, and pending pool.
    * **Deadlock Detection**: Automatically detects and handles lock contention.
    * Entity Indexing for O(1) queries.

*   :material-flash:{ .lg .middle } __Parallel Engine__

    ---

    __File__: `parallel_engine.py`

    * Policy-driven parallel processing.
    * Specialized worker pools for Validation, Indexing, and Batch processing.
    * Automatic data chunking for memory optimization.

*   :material-speedometer:{ .lg .middle } __Advanced Caching__

    ---

    __File__: `caching.py`

    * 3-tier caching: Block, Event, and Entity.
    * Eviction policies: **LRU**, **LFU**, **FIFO**, **TTL**.
    * Speeds up block access by up to **42x**.

</div>

---

## Block Architecture (High-Performance Event Storage)

HieraChain does not store blocks in plain JSON format. Each block internally is a `pyarrow.Table`.

### Key Advantages:

1.  **Memory Efficiency**: Arrow uses optimized memory layout, reducing Python object overhead.
2.  **Blazing Fast Queries**: Searching events by `entity_id` or `event_type` is performed directly in Arrow's C++ layer.
3.  **Consistency**: The `data` field stores the original payload as Binary, ensuring absolute integrity during hashing.

```python
# Example fast query on a Block
entity_events = block.get_events_by_entity("PROD-123")
```

---

## Blockchain & Deadlock Prevention

HieraChain is designed to run in multi-threaded environments. The `Blockchain` integrates a **Deadlock Detector** to monitor lock operations:

*   **Monitor**: Tracks lock wait time (default threshold 3s).
*   **Safe Lock**: The `safe_lock(timeout)` mechanism prevents infinite hangs during resource contention.
*   **Recovery**: Automatically triggers a callback when a deadlock risk is detected.

---

## Multi-tier Caching System

The `BlockchainCacheManager` provides remarkable read operation speedups:

| Cache Type | Default Policy | Performance Improvement |
| :--- | :--- | :--- |
| **Block Cache** | LRU (Least Recently Used) | **~42x** (Block retrieval by index) |
| **Event Cache** | TTL (Time To Live) | Optimized for latest event query APIs. |
| **Entity Cache** | LFU (Least Frequently Used) | **~18.9x** (History tracing of an object) |

---

## Parallel Processing Engine

To process thousands of events per second, Core provides an intelligent parallel processing engine:

*   **Validation Pool**: Dedicated to checking block signatures and Merkle roots.
*   **CPU Intensive Pool**: Uses `ProcessPoolExecutor` for heavy hash computations.
*   **Policy-driven**: The system automatically selects the appropriate pool based on task type (e.g., `indexing` tasks have lower priority than `priority` tasks).

---

## Domain Contract

The `DomainContract` class allows defining business rules:

*   **Lifecycle**: Manages states from `DEVELOPMENT` -> `ACTIVE` -> `DEPRECATED`.
*   **Versioning**: Supports contract version upgrades and data migration.
*   **Storage**: Each contract has its own key-value storage space.

---

## Related

*   [Hierarchical Architecture](../architecture/hierarchy.md)
*   [Performance Benchmarking](../guides/performance.md)
*   [Security Verifiers](./security.md)
