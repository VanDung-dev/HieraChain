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

Proof submission for a Sub-Chain is serialized on that chain while it captures
the current tip, checks for an existing anchor, records the MainChain event,
and verifies durable read-back. Concurrent requests for the same Sub-Chain tip
therefore reuse one proof anchor instead of appending duplicates. This lock is
local to one Sub-Chain object; it is not a distributed lock between processes.

---

## Quarantine Report Signatures

`QuarantineReport.compute_signature(secret_key)` computes HMAC-SHA256 over every field returned by `to_dict()` except `signature`: `msg_type`, `lockdown_type`, `node_id`, `timestamp`, `pending_event_ids`, `last_block_index`, `last_block_hash`, and `total_pending`. The payload is compact UTF-8 JSON with sorted object keys, unescaped Unicode and finite numbers. Event list order is preserved and protected. The digest remains the first 32 hexadecimal characters.

Canonical bytes use `hierachain.serialization.dumps_canonical_json(payload)`, equivalent to standard-library `json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")`. External signers must use the same encoding. Previously issued signatures using another float representation must be signed again from trusted data.

The caller assigns the result to `report.signature`; `verify_signature(secret_key)` checks it with a constant-time comparison. Changing any report field invalidates the signature. A JSON round-trip or reordering object keys preserves verification. Missing or malformed signatures and unsupported payload values return `False`; signing non-finite timestamps raises `ValueError`. `from_dict()` rejects supplied `msg_type` or `lockdown_type` values that do not describe a quarantine report.

Signatures created using the previous three-field payload are rejected. Regenerate reports from trusted data and sign the complete payload; there is no fallback to the old signature format. Callers supply and protect the shared secret. These helpers do not provision keys, enforce report freshness, or automatically authenticate reports in a runtime coordinator.

---

## Related

*   [P2P Networking](./network.md)
*   [Security Identity](./security.md)
*   [Hierarchical Architecture](../architecture/hierarchy.md)

## Concurrent status and lockdown admission

`CrossLevelSyncManager.get_status()` remains active while any overlapping sync or conflict resolution runs. When the group finishes, it reports `failed` if any operation failed, otherwise `complete`. A later independent operation starts a new group. `get_stats()` includes `active_operations`; `reset()` raises `RuntimeError` while work is active. Completion callback errors are logged and do not reverse an already committed proof.

`LockdownMessage.verify_signature()` authenticates only. Before acting on a message, an application dispatcher must call `LockdownMessageGuard.accept(message, secret_key)` and act only when it returns `True`. Keep one guard across requests. It checks the signature and finite timestamp, allows messages up to 60 seconds old and 5 seconds ahead by default, and atomically rejects duplicate signed payloads, including full/truncated signature aliases. Configure `max_age`, `future_skew` and `max_entries` for the dispatcher. When replay storage is full, admission rejects new messages until entries expire instead of evicting active records. Invalid signatures do not consume capacity.

The repository has no lockdown dispatcher. The guard is process-local and does not preserve replay records across restarts or share them between workers. Applications requiring those guarantees must retain replay state in their own dispatcher storage. It does not authenticate `QuarantineReport` admission.
