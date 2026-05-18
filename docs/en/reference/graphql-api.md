---
title: GraphQL API Reference
description: Reference documentation for Query and Mutation fields on the HieraChain GraphQL network.
icon: material/graphql
---

# GraphQL API Reference

## GraphQL API Reference

The system allows direct interaction via the **GraphQL Endpoint**. Core configuration directory: `hierachain/api/graphql/schema.py`. The GraphQL structure is optimized for selective multi-data queries without excessive network resource usage like REST.

### 1. Queries

The GraphQL Schema interface supports powerful hierarchical extraction across Main-Chain and Sub-Chains.

**Get a single Block:**

Query a single Block function locally by chain name and `index`.

```graphql
query GetSingleBlock {
  block(chainName: "sub_chain_finance", blockIndex: 1) {
    index
    hash
    timestamp
    events {
      eventId
      eventType
    }
  }
}
```

**Filter Events with parameters:**

Quick filtering capabilities.

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

Provides a comprehensive view with `chainStatus` (check a single chain) or `allChains` (network dashboard mirror).

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
