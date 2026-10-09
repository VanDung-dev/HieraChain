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

`blocks` and `events` return at most 100 results per field. The default is 100; `limit: 0` returns an empty list. The cap also applies when `limit` is supplied through a GraphQL variable.

`events` reads finalized events in block/row order. On native chains, `entityId` and `eventType` use event indexes; combined filters use the smaller candidate list. Missing indexed values return an empty list without scanning blocks. Only matching results are copied and converted to GraphQL, including their JSON details. `fromTimestamp` and `toTimestamp` are inclusive and accept zero. For time-only queries, Arrow metadata is filtered in batches before payload decoding; this path can still inspect the remaining history when no event matches. Event-type/entity candidates with a selective time filter may also require checking the remaining candidates.

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

**Read the next event page:**

Each event returned by `events` has an opaque `cursor`. Pass the last returned cursor as `after` and retain the same chain and filters. Pagination resumes after that block/row position, so equal timestamps do not cause duplicates or omissions. Native indexed queries seek within the candidate list; unfiltered/time-only native queries start at the cursor's block. Empty results indicate the end for the current filters. Cursors are chain-specific; malformed or cross-chain cursors produce a query error. Pending events are excluded. Pagination is a live read of an append-only chain, not a snapshot across requests; later finalized events may appear on subsequent pages. The `cursor` field is populated by the root `events` query, not nested `block.events`/`blocks.events`.

```graphql
query EventPage($after: String) {
  events(chainName: "main_chain", eventType: "user_registered", limit: 10, after: $after) {
    entityId
    eventType
    cursor
  }
}
```

The type index shares cached event payloads with the existing entity index and is rebuilt during chain recovery. It adds references and row positions in memory; it does not introduce a separate event payload store or remove signature verification. External chain implementations without native indexes use the Arrow/list compatibility path.

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

A Sub-Chain mutation acknowledges submission. `blockIndex` can be the latest existing block index, not the new event's committed position; read finalized events/blocks to verify. The schema supplies no finality or idempotency contract for mutations.
