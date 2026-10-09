---
title: "Core Module"
description: "Core ledger primitives: Block, Blockchain, Merkle Tree, and in-memory caching."
icon: material/cube
---

# Core module (`hierachain/core/*`)

## Overview

The `core` module contains blocks, the base chain, Merkle root calculation and in-memory caches. Blocks use Apache Arrow tables for event storage and filtering. Canonical JSON event bytes determine Merkle roots; canonical headers determine block hashes. `KeyManager` uses `AdvancedCache` for key and permission lookups.

## Components

All core primitives reside in `hierachain/core/`.

### Block (`block.py`)

* Stores event records in a `pyarrow.Table`.
* Filters `entity_id` and `event` with Arrow compute expressions, then decodes matching event payloads into Python dictionaries.
* Calculates deterministic block hashes and Merkle roots.
* Uses Arrow data as the source for both verification and persistence. `to_event_list()` and `to_dict()` return independent event snapshots; changing the input list or an exported snapshot does not change the block.

### Blockchain (`blockchain.py`)

* Coordinates chain state, genesis initialization, and pending event queues.
* Uses `threading.RLock` for chain mutation and indexed queries.
* Maintains entity and event-type indexes for historical event lookups.

Construction requires a fixed signing identity and its operator-approved public key. The genesis block is signed with that identity. `add_event()` copies and validates the event, supplies a timestamp if absent, and returns an event ID for the pending queue. `finalize_block()` signs and validates a block before adding it to the in-memory chain and removing the committed pending events.

The base class has no automatic batch worker, event journal or storage adapter. Ordering and durable storage are supplied by higher-level components; see [Ordering service](../consensus/ordering.md). `Blockchain.add_block()` checks integrity and trusted signatures through `BlockVerifier`; consensus checks belong to the MainChain/SubChain implementations.

### Merkle tree (`merkle_tree.py`)

* Constructs binary Merkle trees from event hashes.
* Exposes the calculated root through `get_root()`.
* Promotes an unpaired node unchanged at each level. Paired nodes are hashed as `SHA256(b"\x01" + left.encode() + right.encode())`, where each child is a hexadecimal hash string.

An empty tree has the SHA-256 hash of empty bytes; a single leaf is its own root. `MerkleTree` has no inclusion-proof generation or verification method. `BlockVerifier.verify_merkle_root()` recomputes the root from a block's events and compares it with the stored root. Cross-chain anchor checks are implemented in the hierarchical layer.

### Cache (`cache.py`)

* Provides an in-memory cache with LRU, LFU, FIFO, and TTL eviction policies.
* `KeyManager` uses it for key and permission lookups.

`AdvancedCache(max_size=10000, eviction_policy="lru")` sets capacity and eviction policy per instance. Expiration is supplied per entry through `set(key, value, ttl=...)`. The `ttl` eviction policy removes expired entries first and falls back to LRU when none have expired.

TTL expiration is lazy: reads reject expired entries; writes at capacity, statistics, key enumeration, and `len(cache)` remove them. `cleanup_ttl()` remains available for explicit cleanup. Cache instances do not create cleanup threads, so discarded caches can be collected. Expired entries in an idle cache can remain allocated until its next operation or collection.

## Block memory and storage layout

The Arrow table has metadata columns for filtering and a binary `data` column for canonical JSON event bytes. `to_event_list()` decodes those bytes to preserve JSON types and nested details. See [Data models](../reference/data-models.md) for the seven-column schema.

`calculate_hash()` hashes `index`, `timestamp`, `previous_hash`, `nonce`, `merkle_root` and `creator_id`. The signature and event table are not direct header fields in that hash; the Merkle root binds the event bytes to the header.

```python
# Query events by entity on a Block instance
entity_events = block.get_events_by_entity("PROD-123")
```

## Blockchain locking

`Blockchain.lock` is a reentrant lock, which allows methods such as `finalize_block()` to call other locked methods in the same thread. Internal `with self.lock` blocks wait for acquisition without a configured timeout. There is no `safe_lock(timeout)`, deadlock detector or contention callback in this class. `get_events_by_filter()` scans the chain without acquiring the lock; callers that need a consistent view during concurrent writes must coordinate access.

## Execution

Block hash and Merkle root calculations run synchronously. Core does not create a worker pool. `verify_batch_signatures()` in `hierachain/security/security_utils.py` uses a shared thread pool for batches of at least four signatures; this does not make block hashing or chain-wide integrity checks parallel.

## Related

* [Hierarchical Architecture](../architecture/hierarchy.md)
* [Storage Module](./storage.md)
* [Security Overview](./security.md)

## Cache mapping and timestamps

`AdvancedCache` implements `MutableMapping` over its eviction store. Iteration, `items()`, `values()`, `update()`, `pop()`, `setdefault()` and `dict(cache)` use the same entries as `get()` and `set()`. Stored `None` is a valid value; absent or expired entries raise `KeyError` on indexing. `get_keys()` returns a live-key snapshot. Consumers should use the `MutableMapping` interface. Keys are normalized to strings.

An explicit block timestamp of `0` is preserved across serialization and hash verification. Only `None` requests the current time.

### JSON serialization

`hierachain.serialization` uses Python standard-library `json`. Writers reject non-finite numbers instead of converting them to `null`; readers reject `NaN`, `Infinity` and float overflow. Integers retain Python integer precision within its configured conversion limit. UTF-8 output is compact; digest and signature payloads use sorted object keys. Unsupported objects require an explicitly configured serializer in components that already support them.

Canonical encoding is part of the integrity contract for hashes, event IDs, Merkle roots, signatures, encrypted metadata AAD and uploaded IPFS content. Changing an encoder's number formatting can change these bytes even when decoded values are equal. Historical roots and signatures are not automatically rewritten or accepted through a fallback encoder. Coordinate encoder changes across nodes and verify existing history before migration. The BFT request digest also uses the shared `dumps_canonical_json()` helper. Decimal values requiring exact decimal arithmetic and large identifiers shared with limited-precision clients should have an explicit string or integer schema.
