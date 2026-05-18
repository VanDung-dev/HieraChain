---
title: "API Module"
description: "Multi-protocol API system: REST v1/v2/v3, GraphQL and WebSocket. Multi-layer security integration and IPFS data management."
icon: material/api
---

# API Module (`hierachain/api/*`)

## Overview

The **API** module is the main communication gateway between the outside world and the HieraChain blockchain core. The system is built on **FastAPI**, providing extremely high performance and simultaneously supporting multiple interaction methods: RESTful, GraphQL, and WebSocket.

### Core Components

* **FastAPI Server (`server.py`)**: Launch point, Middleware configuration, Authentication, and Router integration.
* **Versioned REST API**: Divided into 3 versions (v1, v2, v3) serving different purposes from core to system administration.
* **GraphQL Endpoint**: Provides flexible query capabilities with security mechanisms (Depth/Complexity limit).
* **WebSocket Gateway**: Streams real-time events/blocks using the Publish/Subscribe model.
* **IPFS Integration**: Transparent handling of on-chain and off-chain data (IPFS + AES-256-GCM).

---

## Architecture & Security (Middleware Layer)

HieraChain API implements a multi-layered security Middleware to ensure enterprise data safety:

### HTTP Security

* **Security Headers**: Automatically adds security headers such as CSP (Content Security Policy), HSTS, X-Frame-Options (DENY), and X-Content-Type-Options (nosniff).
* **Payload Limit**: Limits request body size (default 5MB) to prevent DoS attacks.
* **CORS Management**: Controls access from unknown origins, especially strict in Production environments.

### Rate Limiting

Supports two storage backends for Rate Limit counters:

* **In-memory**: Suitable for single-node setups.
* **Redis**: Suitable for cluster nodes requiring synchronized limit state.

*Default*: 60 requests/minute (configurable via `HRC_RATE_LIMIT_REQUESTS_PER_MINUTE`).

### Authentication

Uses `APIKeyVerifier` to check access rights based on API Key. This mechanism can be enabled/disabled via the `HRC_AUTH_ENABLED` environment variable.

---

## REST API Reference

### v1: Core Ledger

Focuses on basic blockchain operations:

* `GET /api/v1/health`: Check node health.
* `GET /api/v1/chains`: List all Main Chains and Sub-Chains.
* `POST /api/v1/chains/{name}/events`: Add an event (automatically handles IPFS if data is large).
* `GET /api/v1/entities/{id}/trace`: Trace an entity across all chains in the hierarchy.
* `GET /api/v1/chains/{name}/blocks`: Get block list (supports pagination and IPFS CID decoding).

### v2: Enterprise Features

Provides advanced tools for complex business processes:

* **Channels**: Create private communication channels between organizations (`POST /api/v2/channels`).
* **Private Data**: Manage Private Data Collections that are not publicly shared on the common ledger.
* **Domain Contracts**: Deploy and execute business-specific smart contracts.
* **Organizations**: Register and manage organizational identities via MSP.

### v3: System & Admin

Dedicated to node management and system operations:

* `POST /api/v3/verify-identity`: Node signs a challenge to prove identity to the management system.
* `GET /api/v3/status`: Detailed report of uptime, active chain count, version, and license status.

---

## GraphQL API

Endpoint: `/graphql`

GraphQL is recommended when clients need complex data queries or bandwidth optimization (field selection).

### Specific Security Mechanisms

* **Query Depth Limit**: Maximum 10 levels of nesting.
* **Complexity Analysis**: Limit of 1000 points per query (calculated based on number of fields and operations).
* **Introspection Control**: Automatically disables schema exploration (`__schema`) in Production environments.

### Query Example (Lazy-loading IPFS)

When querying events, you can decide whether to decrypt data from IPFS via the `resolveCid` parameter.

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

## WebSocket (Real-time Streaming)

Endpoint: `/ws`

HieraChain uses WebSocket to push new data to clients as soon as a block is committed or a new event occurs.

### Main Message Types

* **Client -> Server**
    * `subscribe`: Subscribe to notifications from a specific chain or by event type.
    * `ping`: Keep connection alive.
* **Server -> Client**
    * `block_added`: Notification of a new block with condensed data.
    * `event`: Pushes detailed event information to subscribers.
    * `subscribed`: Confirms successful subscription.

---

## Blockchain Explorer

Built-in at `blockchain_explorer.py`, the explorer provides a dashboard interface for operators:

* **Monitor**: Track block generation speed and events in real time.
* **Visualizer**: Visualize the hierarchical tree structure between Main Chain and Sub-Chains.
* **IPFS Decoder**: Allows authorized administrators to quickly decode CIDs directly in the browser.

---

## Observability

* **X-Request-ID**: Each request is assigned a unique UUID in the header for log tracing.
* **Metrics**: Built-in `/metrics` endpoint (Prometheus format) to track:

    * Number of successful/failed requests.
    * Average response latency.
    * API server memory and CPU status.

---

## Quick Usage Guide (curl)

### Write an Event to a Chain

```bash
curl -X POST http://localhost:2661/api/v1/chains/my_chain/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_secret_key" \
  -d '{
    "entity_id": "ITEM-123",
    "event_type": "quality_check",
    "details": {"status": "passed", "inspector": "AI-Agent"}
  }'
```

### Trace an Entity

```bash
curl "http://localhost:2661/api/v1/entities/ITEM-123/trace?resolve_cid=true"
```

---

## Related

* [Hierarchical Structure](./hierarchical.md)
* [Storage & IPFS Integration](./storage.md)
* [Security & Identity](../security/encryption-keys.md)
