---
title: "Cross-Chain Operations"
description: "How to initiate and recover durable Two-Phase Commit (2PC) operations."
icon: material/swap-horizontal
---

# Cross-Chain Operations (2PC)

## Purpose

`CrossChainTransactionManager` coordinates a transaction between two `DomainChain` participants. Its coordinator-owned journal stores transaction metadata and the durable commit decision separately from each chain's ordering event journal.

## Transaction states

- **`PENDING`**: The coordinator has created the transaction.
- **`PREPARED`**: Both participants accepted the prepare request; no commit decision has been made yet.
- **`IN_DOUBT`**: The coordinator cannot confirm completion. Before a durable COMMIT decision it retries abort; after that decision it retries commit.
- **`COMMITTED`**: Both participants acknowledged that their operation events were fsynced to their ordering journals. Block finalization may still be running asynchronously.
- **`ROLLED_BACK`**: Both participants acknowledged abort before any durable COMMIT decision.
- **`FAILED`**: The transaction could not start, for example because a named chain is missing or does not support 2PC.

## Transaction flow

1. The coordinator fsyncs a `begin` record before preparing either participant.
2. It prepares the source and destination, then fsyncs a `prepared` record.
3. It fsyncs the COMMIT decision before calling either participant's `commit_transaction()`.
4. Each participant acknowledges only after its transaction-tagged start and completion events have been accepted by its ordering journal.
5. After both acknowledgments, the coordinator fsyncs `committed` and exposes `COMMITTED`.

If prepare fails, the coordinator attempts abort on both participants. It reports `ROLLED_BACK` only if both return `True`; otherwise it records `IN_DOUBT` and retries abort later. After a durable COMMIT decision, it never calls rollback. A failed commit remains `IN_DOUBT` and is retried forward.

## Initiate an operation

Use the `HierarchyManager` coordinator so its durable journal and recovery state remain shared:

```python
tx_id = hierarchy_manager.initiate_cross_chain_transaction(
    source_chain_name="sub_chain_finance",
    dest_chain_name="sub_chain_logistics",
    payload={
        "entity_id": "PKG-099238",
        "operation_type": "transfer",
        "details": {"quantity": 500},
    },
)

transaction = hierarchy_manager.transaction_manager.get_transaction(tx_id)
```

The entity must be registered on both chains and the operation payload must pass both participants' validation.

## Recover unresolved operations

The coordinator retries durable decisions at startup and when participants are registered. To retry after a runtime failure:

```python
hierarchy_manager.transaction_manager.retry_pending()
```

Persisted chains named by unresolved 2PC records are restored as `DomainChain` participants. Other persisted chains remain generic `SubChain` instances. If a generic placeholder must be promoted explicitly, call `create_sub_chain()` with its existing name and domain type; the replacement connects before the placeholder shuts down.

After a durable COMMIT, the coordinator's `prepared` record confirms both participants validated the payload before the decision. Recovery restores participant input from that payload and skips operation events already marked in the ordering journal, so it does not depend on volatile entity registries being restored.
