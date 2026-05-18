---
title: "Cross-Chain Transactions"
description: "Guide to Two-Phase Commit (2PC) mechanism and distributed transaction coordination."
icon: material/swap-horizontal
---

# Cross-Chain Transactions

## Purpose

HieraChain's hierarchical network consists of multiple independent Sub-chains serving different domains. To ensure integrity and atomicity when coordinating data flows or asset transfers across two (or more) different systems, HieraChain integrates a coordination mechanism called **Two-Phase Commit (2PC)**.

This mechanism is primarily managed by the `CrossChainTransactionManager` module at `hierachain/hierarchical/transaction_manager.py`.

### 1. Transaction State Lifecycle

Each cross-chain transaction moves sequentially through the following states to prevent loss:

* **`PENDING`**: Transaction has been initialized, network is waiting to execute the main operation.
* **`PREPARED`**: Both source and destination chains have committed that conditions are sufficient for execution, resources have been successfully locked.
* **`COMMITTED`**: Transaction completed on all network chains with consensus.
* **`ROLLED_BACK`**: Transaction cancelled due to failure in one of the locks. Locked resources on branches will be rolled back to previous version.
* **`FAILED`**: Transaction failed completely (likely due to internal TCP connection failure or critical logic error).

### 2. Two-Phase Commit (2PC) Model

In `CrossChainTransactionManager`, `_execute_2pc(transaction)` clearly allocates the main process to handle transactions. The core logic consists of two phases:

#### Phase 1: Prepare Phase

* The manager retrieves objects from `get_sub_chain()` of HierarchyManager.
* Calls `prepare_transaction(tx_id, payload, is_source=True)` on the **Source** chain to lock source resources.
* Then calls `prepare_transaction` on the **Destination** chain to mark the transaction receipt.
* Goal of Phase 1: Force all participating chains to commit that they can perform the change.
* If Source or Destination chain cannot Prepare successfully (e.g. due to lock balance errors), the system immediately proceeds to `_rollback()`.

#### Phase 2: Commit Phase

* Only executed if Phase 1 returns success for all participants.
* Module calls `commit_transaction(tx_id)` on the Source chain.
* Simultaneously performs the same on the Destination chain structure for final Commit.
* At this step, the actual block will be created on both Sub-chains to finalize the data exchange.
* If an error occurs during the Commit process (though rare), the transaction state is flagged as `FAILED` to await manual recovery tools via that ID.

### 3. Command Initialization Guide

When needing to issue a command via DApp or external Module, developers access the following API/Function:

```python
# Get instance from existing HierarchyManager
manager = CrossChainTransactionManager(hierarchy_manager=hierarchy_manager_instance)

# Execute initiate transaction command
tx_id = manager.initiate_transaction(
    source_chain_name="sub_chain_finance",
    dest_chain_name="sub_chain_logistics",
    payload={
        "event_name": "asset_transfer",
        "asset_id": "PKG-099238",
        "amount": 500
    }
)
```

This will trigger `_execute_2pc` automatically and synchronously within the management logic without requiring additional client-side operations.
