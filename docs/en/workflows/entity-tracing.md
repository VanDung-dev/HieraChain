---
title: "Entity tracing"
description: "Query finalized entity histories across registered Sub-Chains, assemble timelines and understand query costs."
icon: material/map-marker-path
---

# Entity tracing

## Query path

`HierarchyManager.trace_entity_across_chains(entity_id)` delegates to `_trace_entity_history()` in `hierachain/hierarchical/hierarchy_manager/organization.py`. It visits registered Sub-Chains sequentially and returns a dictionary containing chains with nonempty histories. It does not merge or sort a global timeline itself.

`SubChain.get_entity_history()` retrieves finalized events and sorts that chain's result by timestamp. Native `Blockchain` stores entity-index entries containing block/row positions and cached event payloads. The index avoids a full block scan, but copying m matching events costs O(m), and per-chain sorting costs O(m log m). Cross-chain lookup also visits each registered chain. Indexes are rebuilt during recovery.

## Example

After [Quickstart](../getting-started/quickstart.md), the application can merge results:

```python
# manager is the configured HierarchyManager from the quickstart.
history_by_chain = manager.trace_entity_across_chains("PROD-001")
timeline = sorted(
    (
        {"chain": name, **event}
        for name, events in history_by_chain.items()
        for event in events
    ),
    key=lambda event: event.get("timestamp", 0),
)
```

## Errors and HTTP interface

An unknown entity produces an empty dictionary. The manager ignores a chain lacking the history API (`AttributeError`); it does not catch every storage or query error and promise partial success.

`EntityTracer` in `hierachain/domains/utils/entity_tracer.py` provides richer tracing and timeline aggregation. REST uses `GET /api/ledger/entities/{entity_id}/trace`, optionally with `chain_name` and `resolve_cid`. Pending Sub-Chain events are not finalized history. See [Ledger API](../reference/api-ledger.md).

## Related

* [Integrity validation](integrity-validation.md)
* [ERP integration](erp-integration.md)
