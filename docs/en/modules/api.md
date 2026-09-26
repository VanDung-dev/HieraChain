---
title: "API Module"
description: "Multi-protocol API system: REST ledger/business/admin, GraphQL and WebSocket. Multi-layer security integration and IPFS data management."
icon: material/api
---

# API Module (`hierachain/api/*`)

## Overview

The API module handles communication between external clients and the HieraChain core. It is built on FastAPI and supports REST, GraphQL, and WebSocket. Performance is the main design goal, so the same service can serve all three protocols without separate deployments.

### Core components

* FastAPI server (`server.py`) is the entry point. It sets up middleware, authentication, and routers.
* Versioned REST API has three groups (ledger, business, admin) for core operations, business features, and system administration.
* GraphQL endpoint offers flexible field selection with depth and complexity limits.
* WebSocket gateway streams blocks and events to subscribers using publish/subscribe.
* IPFS integration handles off-chain data with AES-256-GCM encryption. Large payloads stay off chain and only the CID is stored on chain.

---

## Architecture and security

The API uses layered middleware. Each request passes through the same checks before it reaches a handler.

### HTTP security

* Security headers are added to every response, including CSP, HSTS, X-Frame-Options set to DENY, and X-Content-Type-Options set to nosniff.
* Payload limit caps request bodies at 5 MB by default. This helps prevent DoS with large payloads.
* CORS controls which origins can call the API. Production requires an explicit allow list.

### Rate limiting

Rate limiting counts requests per key and supports two backends:

* In-memory for single-node deployments.
* Redis for clusters where counters must stay in sync.

The default limit is 100 requests per minute, configured with `HRC_RATE_LIMIT_RPM`.

### Authentication

`APIKeyVerifier` checks the `X-API-Key` header. Enable or disable it with `HRC_AUTH_ENABLED`.

---

## REST API reference

### ledger: core ledger

These endpoints interact directly with ledger state:

* `GET /api/ledger/health` checks node health.
* `GET /api/ledger/network/ping/{target_id}` sends a direct ping to a target peer.
* `GET /api/ledger/chains` lists Main Chains and Sub-Chains.
* `POST /api/ledger/chains/{chain_name}/create` provisions a new sub-chain.
* `GET /api/ledger/chains/{chain_name}/stats` retrieves block, event, and proof counts.
* `POST /api/ledger/chains/{chain_name}/events` submits an event, offloading oversized payloads to IPFS.
* `POST /api/ledger/chains/{chain_name}/submit-proof` submits cryptographic proofs from a sub-chain to the main chain.
* `GET /api/ledger/chains/{chain_name}/blocks` lists blocks with pagination and optional CID decoding.
* `GET /api/ledger/chains/{chain_name}/blocks/{index_or_hash}` fetches a single block by index or hash.
* `GET /api/ledger/entities/{id}/trace` traces an entity across the chain hierarchy.

### business: enterprise features

These endpoints support business workflows:

* Channels create private communication paths between organizations (`POST /api/business/channels`).
* Private data collections hold data that is not shared on the common ledger.
* Domain contracts deploy and run business-specific smart contracts.
* Organizations register and manage identities through MSP.

### admin: system and admin

These endpoints are for node and system operations:

* `POST /api/admin/verify-identity` lets a node sign a challenge to prove its identity.
* `GET /api/admin/status` returns uptime, chain counts, version, and license status.
* `POST /api/admin/chains/{chain_name}/secure-events` submits high-integrity events requiring synchronous signature verification.

---

## GraphQL API

Endpoint: `/graphql`

Use GraphQL when clients need to select specific fields or reduce payload size.

### Security limits

* Query depth is limited to 10 levels.
* Complexity is limited to 1000 points per query, based on field and operation counts.
* Introspection (`__schema`) is disabled in production.

### Query example (lazy-loading IPFS)

You can choose whether to fetch and decrypt IPFS data with `resolveCid`.

```graphql
query {
  events(chainName: "supply_chain", entityId: "PROD-001", resolveCid: true) {
    eventType
    details  # Will be automatically fetched from IPFS and decrypted if needed
    timestamp
    isOffchain
  }
}
```

---

## WebSocket (real-time streaming)

Connect to `/ws`. To select a chain when connecting, pass `chain_name`, for example `/ws?chain_name=supply_chain`.

The server pushes data as soon as a block is committed or an event arrives.

### Main message types

* Client to server
    * `subscribe` subscribes to a chain or event type.
    * `ping` keeps the connection alive.
* Server to client
    * `block_added` notifies about a new block with condensed data.
    * `event` pushes event details to subscribers.
    * `subscribed` confirms the subscription.

---

## Blockchain explorer

Built in at `blockchain_explorer.py`, the explorer gives operators a dashboard:

* Monitor shows block production rate and event flow in real time.
* Visualizer renders the tree between Main Chain and Sub-Chains.
* IPFS decoder lets authorized admins decode CIDs in the browser.

---

## Observability

* `X-Request-ID` adds a UUID to each request for log tracing.
* `/metrics` exposes Prometheus metrics, including:
    * Count of successful and failed requests.
    * Average response latency.
    * Memory and CPU status of the API server.

---

## Quick usage guide (curl)

### Write an event to a chain

```bash
curl -X POST http://localhost:2661/api/ledger/chains/my_chain/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_key" \
  -d '{
    "entity_id": "ITEM-123",
    "event_type": "quality_check",
    "details": {"status": "passed", "inspector": "AI-Agent"}
  }'
```

### Trace an entity

```bash
curl "http://localhost:2661/api/ledger/entities/ITEM-123/trace?resolve_cid=true"
```

---

## Related

* [Hierarchical Structure](./hierarchical.md)
* [Storage & IPFS Integration](./storage.md)
* [Security & Identity](../security/encryption-keys.md)
