---
title: GraphQL API Reference
description: Reference documentation for Query and Mutation fields on the HieraChain GraphQL network.
icon: material/graphql
---

# GraphQL API Reference

The GraphQL endpoint exposes the Query and Mutation fields defined in `hierachain/api/graphql/schema.py`. Clients can request selected fields across Main-Chain and Sub-Chains.

### 1. Queries

Use these queries to read blocks, events, and chain status across Main-Chain and Sub-Chains.

**Get a single Block:**

Retrieve a block by chain name and `index`.

```graphql
query GetSingleBlock {
  block(chainName: "sub_chain_finance", blockIndex: 1) {
    index
    hash
    timestamp
    events {
      entityId
      eventType
    }
  }
}
```

**Filter Events with parameters:**

Filter events by chain name, event type, and result limit.

```graphql
query FilterEvents {
  events(
    chainName: "main_chain", 
    limit: 10, 
    eventType: "user_registered"
  ) {
    entityId
    details
    signature
  }
}
```

**Blockchain Status:**

Use `chainStatus` to check one chain or `allChains` to retrieve status for every chain.

```graphql
query OverallSystem {
  allChains {
    chainName
    blockCount
    latestBlockHash
    status
  }
}
```

### 2. Mutations

The GraphQL Schema supports Mutation functionality for submitting Events directly into sub-chain or main-chain.

**Input Parameters (`AddEventInput`):**
- `chainName` (Required String)
- `entityId` (Required String)
- `eventType` (Required String)
- `details` (Optional String - JSON stringified)

**Example:**

```graphql
mutation CreateNewEvent {
  addEvent(event: {
    chainName: "sub_chain_logistics",
    entityId: "driver_443",
    eventType: "delivery_confirmed",
    details: "{\"status\": \"ok\", \"location\": \"zone-b\"}"
  }) {
    success
    blockIndex
    error
  }
}
```
