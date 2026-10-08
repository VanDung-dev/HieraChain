---
title: "Core Module"
description: "Core ledger primitives: Block, Blockchain, Merkle Tree, and in-memory caching."
icon: material/cube
---

# Core Module (`hierachain/core/*`)

## 1. Overview

The `core` module contains foundational data structures for the ledger. Blocks store events in Apache Arrow tables for fast in-memory filtering and deterministic hashing. Cryptographic Merkle trees prove event inclusion. `AdvancedCache` provides per-instance in-memory caching, used by `KeyManager` for key and permission lookups.

## 2. Foundational components

All core primitives reside in `hierachain/core/`.

### 2.1 Block (`block.py`)

* Stores event records in a `pyarrow.Table`.
* Queries event fields with Arrow compute expressions rather than Python loops.
* Calculates deterministic block hashes and Merkle roots.
* Uses Arrow data as the source for both verification and persistence. `to_event_list()` and `to_dict()` return independent event snapshots; changing the input list or an exported snapshot does not change the block.

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

TTL expiration is lazy: reads reject expired entries; writes at capacity, statistics, key enumeration, and `len(cache)` remove them. `cleanup_ttl()` remains available for explicit cleanup. Cache instances do not create cleanup threads, so discarded caches can be collected. Expired entries in an idle cache can remain allocated until its next operation or collection.

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

## Cache mapping and timestamps

`AdvancedCache` implements `MutableMapping` over its eviction store. Iteration, `items()`, `values()`, `update()`, `pop()`, `setdefault()` and `dict(cache)` use the same entries as `get()` and `set()`. Stored `None` is a valid value; absent or expired entries raise `KeyError` on indexing. `get_keys()` returns a live-key snapshot. The cache is no longer a `dict` subclass; consumers should check `MutableMapping` instead. Keys are normalized to strings.

An explicit block timestamp of `0` is preserved across serialization and hash verification. Only `None` requests the current time.

### JSON serialization

`hierachain.serialization` uses Python standard-library `json`. Writers reject non-finite numbers instead of converting them to `null`; readers reject `NaN`, `Infinity` and float overflow. Integers retain Python integer precision within its configured conversion limit. UTF-8 output is compact; digest and signature payloads use sorted object keys. Unsupported objects require an explicitly configured serializer in components that already support them.

The BFT request digest retains its established standard-library format. Other hashes, event IDs, Merkle roots, signature payloads, encrypted metadata AAD and newly uploaded IPFS content can differ from earlier serializers when number formatting differs, even if decoded values are equal. Existing JSON content remains readable, but historical roots or signatures are not automatically rewritten or accepted with a fallback encoder. Coordinate node upgrades and start a fresh ledger for this refactoring branch, or explicitly migrate and verify existing history before using it. Decimal values requiring exact decimal arithmetic and large identifiers shared with limited-precision clients should have an explicit string or integer schema.
