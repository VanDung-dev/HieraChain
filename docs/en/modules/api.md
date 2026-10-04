---
title: "API Module"
description: "Multi-protocol API system: REST ledger/business/admin, GraphQL and WebSocket. Multi-layer security integration and IPFS data management."
icon: material/api
---

# API Module (`hierachain/api/*`)

## Overview

The API module handles communication between external clients and the HieraChain core. It is built on FastAPI and supports REST, GraphQL, and WebSocket. Performance is the main design goal, so the same service can serve all three protocols without separate deployments.

### Core components

Importing API client helpers, such as `hierachain.api.storage.ipfs_client`, does not create the server application. The `app` and `create_app` exports load the server when requested; production authentication requirements remain enforced. API lifespan shutdown closes its hierarchy manager and resets the lazy manager/tracer providers, including cleanup after a P2P startup failure.

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

`APIKeyVerifier` checks the `X-API-Key` header for HTTP and WebSocket access. Production requires `HRC_AUTH_ENABLED=true` and a provisioned `HRC_API_KEYS_FILE`; dev/test can disable authentication. With authentication enabled, GraphQL checks scopes for every operation: chain and block queries require `chains`, event queries and `addEvent` require `events`, and a block query that selects nested events requires both scopes. WebSocket streams contain both block and event messages, so connecting and subscribing requires `chains` and `events` (or `all`). Production GraphQL and WebSocket requests fail closed if the app has no enabled verifier or the verifier returns no auth context.

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
* Private collection metadata can be managed, but `POST /api/business/private-data` currently returns HTTP 501 because this API has no private-data store. It does not accept inline values or IPFS references as stored data.
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

### Query example

Event queries require the `events` permission. Block and chain queries require `chains`; selecting events nested under a block requires both.

```graphql
query {
  events(chainName: "supply_chain", entityId: "PROD-001", limit: 20) {
    eventType
    details
    timestamp
  }
}
```

---

## WebSocket (real-time streaming)

Connect to `/ws`. To select a chain when connecting, pass `chain_name`, for example `/ws?chain_name=supply_chain`.

When authentication is enabled, send the `X-API-Key` header in the WebSocket handshake. The connection and each subscription require both `chains` and `events` permissions because the current stream sends both kinds of messages to chain subscribers. The server pushes data as soon as a block is committed or an event arrives.

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

GraphQL reads Arrow events as rows and awaits asynchronous field resolvers, including event details. Nested block events require both `chains` and `events` scopes. Unknown chain names return no query result and reject mutations; they do not fall back to the main chain.

### JSON encoding

Explicit JSON responses and HTTP exception handlers use FastAPI/Starlette `JSONResponse`. Default responses and response models retain FastAPI/Pydantic validation, serialization and OpenAPI schemas. Request-validation errors retain status `422` and the `detail` list. WebSocket messages use standard-library JSON encoded as UTF-8 text frames.
