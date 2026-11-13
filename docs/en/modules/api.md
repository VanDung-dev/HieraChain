---
title: "API Module"
description: "Multi-protocol API system: REST ledger/business/admin and WebSocket. Multi-layer security integration and IPFS data management."
icon: material/api
---

# API Module (`hierachain/api/*`)

## Overview

The API module handles communication between external clients and the HieraChain core. It is built on FastAPI and supports REST and WebSocket. Performance is the main design goal, so the same service can serve both protocols without separate deployments.

### Core components

Importing API client helpers, such as `hierachain.api.storage.ipfs_client`, does not create the server application. The `app` and `create_app` exports load the server when requested; production authentication requirements remain enforced. API lifespan shutdown closes its hierarchy manager and resets the lazy manager/tracer providers, including cleanup after a P2P startup failure.

* FastAPI server (`server.py`) is the entry point. It sets up middleware, authentication, and routers.
* Versioned REST API has three groups (ledger, business, admin) for core operations, business features, and system administration.
* WebSocket gateway manages subscriptions and broadcast helpers; Sub-Chain and channel event submission calls `broadcast_event()`, while block-commit notifications require an application call to `broadcast_new_block()`.
* IPFS integration handles off-chain data with AES-256-GCM encryption. Large payloads stay off chain and only the CID is stored on chain.

## Architecture and security

The API uses layered middleware. Each request passes through the same checks before it reaches a handler.

### HTTP security

* HTTP middleware adds CSP, X-Frame-Options set to DENY and X-Content-Type-Options set to nosniff. It does not add HSTS; configure that header at the HTTPS reverse proxy.
* Payload middleware limits POST/PUT/PATCH bodies to 1 MiB. It checks a supplied Content-Length and reads the stream when that header is absent.
* CORS controls which origins can call the API. Production requires an explicit allow list.

### Rate limiting

Rate limiting counts requests per key and supports two backends:

* In-memory for single-node deployments.
* Redis for clusters where counters must stay in sync.

The default limit is 100 requests per minute, configured with `HRC_RATE_LIMIT_RPM`.

### Authentication

`APIKeyVerifier` checks the `X-API-Key` header for HTTP and WebSocket access. Production requires `HRC_AUTH_ENABLED=true` and a provisioned `HRC_API_KEYS_FILE`; dev/test can disable authentication. WebSocket streams contain both block and event messages, so connecting and subscribing requires `chains` and `events` (or `all`). Production WebSocket requests fail closed if the app has no enabled verifier or the verifier returns no auth context.

## REST API reference

### ledger: core ledger

These endpoints interact directly with ledger state:

* `GET /api/ledger/health` checks node health.
* `GET /api/ledger/network/ping/{target_id}` sends a direct ping to a target peer.
* `GET /api/ledger/chains` lists Main Chains and Sub-Chains.
* `POST /api/ledger/chains/{chain_name}/create` provisions a new sub-chain and requires an authenticated user with `chains:manage`.
* `GET /api/ledger/chains/{chain_name}/stats` retrieves block, event, and proof counts.
* `POST /api/ledger/chains/{chain_name}/events` submits an event, offloading oversized payloads to IPFS. A supplied `details_cid` requires a nonempty, 24-character hexadecimal `details_nonce`; omission or null returns HTTP 422. When a signature is supplied, the API verifies it over the canonical request payload, retains `signature_content`, and preserves the signing identity as `sender`; `submitted_by` is the authenticated API-key user. Production rejects unsigned events with HTTP 422. Legacy signatures cover `details.payload` when it is a string; the submission acknowledgement precedes certification.
* `POST /api/ledger/chains/{chain_name}/submit-proof` submits cryptographic proofs from a sub-chain to the main chain.
* `GET /api/ledger/chains/{chain_name}/blocks` lists blocks with pagination and optional CID decoding.
* `GET /api/ledger/chains/{chain_name}/blocks/{index_or_hash}` fetches a single block by index or hash.
* `GET /api/ledger/entities/{id}/trace` traces an entity across the chain hierarchy.

### business: enterprise features

These endpoints support business workflows:

* Channels create private communication paths between organizations (`POST /api/business/channels`). Private collections are managed per channel (`POST /api/business/channels/{channel_id}/private-collections`), require `channels:manage`, and are delegated to `Channel.create_private_collection(...)`.
* Organizations and members register through the hierarchical organization service (`POST /api/business/organizations`, `POST /api/business/organizations/{org_id}/members`).

### admin: system and admin

These endpoints are for node and system operations:

* `POST /api/admin/verify-identity` lets a node sign a 1–256 character hex challenge to prove its identity; attempts are limited to 10 per minute per client IP in each API process.
* `GET /api/admin/status` is exempt from API-key authentication and returns uptime, chain counts, version, and a hardcoded license flag.
* `POST /api/admin/chains/{chain_name}/secure-events` checks the canonical signature synchronously, then journals and queues the event. HTTP 200 returns `status="queued"`, an ordering event ID in `event_hash`, and the acknowledgement time in `timestamp`; clients expecting `committed` must update. This response does not establish block commitment. Ordering and journal replay reverify the original `signature_content` and its binding to the ordered fields. Queue backpressure returns HTTP 503 with `event_id` and `journaled` in `detail`.

## WebSocket (real-time streaming)

Connect to `/ws`. To select a chain when connecting, pass `chain_name`, for example `/ws?chain_name=supply_chain`.

When authentication is enabled, send the `X-API-Key` header in the WebSocket handshake. The connection and each subscription require both `chains` and `events` permissions because the current stream sends both kinds of messages to chain subscribers. Sub-Chain and channel event submission call `broadcast_event()` automatically. Block-commit paths do not call `broadcast_new_block()`; an application must supply that block notification integration.

### Main message types

* Client to server
    * `subscribe` subscribes to a chain or event type.
    * `ping` keeps the connection alive.
* Server to client
    * `block_added` notifies about a new block with condensed data.
    * `event` pushes event details to subscribers.
    * `subscribed` confirms the subscription.

## Observability

* `X-Request-ID` adds a UUID to each request for log tracing.
* With `HRC_METRICS_ENABLED=true`, `/metrics` exposes the default `prometheus_client` registry. Default process/runtime collectors depend on the platform. The API does not register HTTP success/failure counters, latency histograms or ledger throughput collectors; add those through application instrumentation.

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

## Related

* [Hierarchical Structure](./hierarchical.md)
* [Storage & IPFS Integration](./storage.md)
* [Security & Identity](../security/encryption-keys.md)


### JSON encoding

Explicit JSON responses and HTTP exception handlers use FastAPI/Starlette `JSONResponse`. Default responses and response models retain FastAPI/Pydantic validation, serialization and OpenAPI schemas. Request-validation errors retain status `422` and the `detail` list. WebSocket messages use standard-library JSON encoded as UTF-8 text frames.
