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

## Quarantine Report Signatures

`QuarantineReport.compute_signature(secret_key)` computes HMAC-SHA256 over every field returned by `to_dict()` except `signature`: `msg_type`, `lockdown_type`, `node_id`, `timestamp`, `pending_event_ids`, `last_block_index`, `last_block_hash`, and `total_pending`. The payload is compact UTF-8 JSON with sorted object keys, unescaped Unicode and finite numbers. Event list order is preserved and protected. The digest remains the first 32 hexadecimal characters.

Canonical bytes use `orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)`. External signers must use the same encoding. Float formatting can differ from Python's standard JSON serializer; reports with differing encodings must be signed again from trusted data.

The caller assigns the result to `report.signature`; `verify_signature(secret_key)` checks it with a constant-time comparison. Changing any report field invalidates the signature. A JSON round-trip or reordering object keys preserves verification. Missing or malformed signatures and unsupported payload values return `False`; signing non-finite timestamps raises `ValueError`. `from_dict()` rejects supplied `msg_type` or `lockdown_type` values that do not describe a quarantine report.

Signatures created using the previous three-field payload are rejected. Regenerate reports from trusted data and sign the complete payload; there is no fallback to the old signature format. Callers supply and protect the shared secret. These helpers do not provision keys, enforce report freshness, or automatically authenticate reports in a runtime coordinator.

---

## Related

*   [P2P Networking](./network.md)
*   [Security Identity](./security.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)
