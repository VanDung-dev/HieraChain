---
title: "Entity Tracing"
description: "Cross-chain entity auditing and tracking utility to reconstruct complete event lineages."
icon: material/map-marker-path
---

# Entity Tracing

## Overview

Since the same physical entity (e.g., product `SKU-001`, contract `C-2024`) may generate events across multiple Sub-Chains over its lifecycle, HieraChain provides **cross-chain entity tracing** to reconstruct a complete, immutable audit trail for any `entity_id`.

Each Sub-Chain maintains an in-memory `entity_event_index` keyed by `entity_id`, enabling **O(1) lookup** without full chain scan.

---

## Flow Diagram

```mermaid
flowchart TB
    CLIENT["🖥️ Client / Auditor\ntrace_entity_across_chains(entity_id)"]
    HM["🏛️ HierarchyManager"]

    subgraph SubChains["All Registered Sub-Chains (parallel query)"]
        SC1["📦 supply_chain\nget_entity_history(entity_id)"]
        SC2["📦 logistics\nget_entity_history(entity_id)"]
        SC3["📦 finance\nget_entity_history(entity_id)"]
        SCN["📦 ..."]
    end

    AGG["🔀 Aggregate Results\n{ chain_name: [events] }"]
    SORT["🕒 Sort by timestamp\nacross all chains"]
    OUT["📋 Complete Entity Timeline"]

    CLIENT --> HM
    HM --> SC1
    HM --> SC2
    HM --> SC3
    HM --> SCN
    SC1 --> AGG
    SC2 --> AGG
    SC3 --> AGG
    SCN --> AGG
    AGG --> SORT --> OUT
```

---

## Real-World Example

```
Entity: product-SKU-001 (Industrial sensor batch)

Timeline reconstructed across chains:
────────────────────────────────────────────────────────
[supply_chain]  block 3   quality_check      → passed
[supply_chain]  block 7   packaging_complete → confirmed
[logistics]     block 2   shipment_dispatch  → warehouse A → B
[logistics]     block 9   customs_cleared    → port XYZ
[finance]       block 4   invoice_issued     → INV-2024-0471
[finance]       block 12  payment_confirmed  → ref: WIRE-9821
────────────────────────────────────────────────────────
```

---

## Entity Index Structure

Each Sub-Chain maintains an in-memory `entity_event_index`:

```python
entity_event_index = {
    "product-SKU-001": [
        {"block_index": 3, "event": {"event": "quality_check", "timestamp": 1714000000.0, ...}},
        {"block_index": 7, "event": {"event": "packaging_complete", "timestamp": 1714003600.0, ...}},
    ]
}
```

Events are indexed on write (`add_block()`), so reads are O(1) per chain. Aggregation across n chains is O(n).

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Call** | Client calls `HierarchyManager.trace_entity_across_chains(entity_id)` |
| **2. Fan-out** | HierarchyManager queries all registered Sub-Chains in parallel |
| **3. Per-chain lookup** | Each Sub-Chain calls `get_entity_history(entity_id)` → O(1) index lookup |
| **4. Aggregate** | Results collected as `{ chain_name: [event_list] }` |
| **5. Sort** | Events sorted by `timestamp` across all chains to form chronological timeline |
| **6. Return** | Full timeline returned to caller |

---

## Error Handling

| Condition | Behavior |
|:----------|:---------|
| Entity not found in any chain | Returns empty dict `{}` |
| Sub-Chain unavailable | That chain's result is `[]`; other chains still queried |
| Entity index not yet built (startup) | Falls back to full chain scan; logs warning |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Entry point | `HierarchyManager.trace_entity_across_chains()` | `hierarchical/hierarchy_manager.py` |
| Per-chain trace | `SubChain.get_entity_history()` | `hierarchical/sub_chain.py` |
| Advanced trace | `EntityTracer.trace_entity()` | `domains/generic/utils/entity_tracer.py` |
| Index update | `SubChain._update_event_statistics()` | `hierarchical/sub_chain.py` |
| REST API | `GET /ledger/entities/{entity_id}/trace` | `api/ledger/routes.py` |

---

## Related

- [System Integrity Validation](./integrity-validation.md): validates the chains being traced
- [ERP Integration Sync](./erp-integration.md): ERP events are what gets traced
