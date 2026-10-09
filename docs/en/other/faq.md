---
title: "Frequently Asked Questions"
description: "FAQ about installation, configuration, API, security, performance, and storage for HieraChain."
icon: material/frequently-asked-questions
---

# Frequently Asked Questions

## How do I start a node?

Provision an identity, trusted-key map and database using [Quickstart](../getting-started/quickstart.md), then run `python -m hierachain` or `hrc node start`. The default API port is 2661. `/api/ledger/health` is liveness; `/api/ledger/ready` checks hierarchy recovery.

## How do I enable authentication?

Set `HRC_AUTH_ENABLED=true` before startup and use `X-API-Key` (or `HRC_API_KEY_NAME`). Production requires a readable, nonempty `HRC_API_KEYS_FILE` with provisioned keys, user IDs and permissions. See [Configuration](../reference/config.md).

## Does an event ID mean the block is committed?

No. Sub-Chain acceptance journals and queues the event. Read finalized blocks/events before relying on commitment. MainChain proof submission confirms durable signed proof storage and readback when successful.

## What are MainChain and Sub-Chains?

Sub-Chains store business events. MainChain anchors their block proofs. The proof root is the block event Merkle root; `WorldState.get_state_root()` is a separate diagnostic projection root.

## What format does the event use?

REST/SDK requests use `entity_id`, `event_type` and a JSON object `details`. Internal events use `event`. The API assigns the timestamp. Arrow exposes string-valued detail columns while canonical event bytes preserve the payload for recovery.

## Can I use Redis as the ledger backend?

Hierarchical durable storage requires SQLite or PostgreSQL. Redis is available for auxiliary adapters, authentication state and rate limits; hierarchical startup rejects it as signed-block storage. Memory is process-local.

## Are ZK, contracts, private data and ERP production-ready?

Production ZK proving/verifying, contract execution and private-data writes are unimplemented. Contract execution/private-data writes return HTTP 501. Built-in vendor ERP connectors are simulation-only; real adapters must be supplied by the application.

## How do I investigate latency or 503 errors?

Inspect API rate/payload limits, Redis availability, ordering event-pool/RAM limits and storage logs. PoA defaults to zero added spacing, but batching and durable I/O still take time. See [Performance](../guides/performance.md).

## How do I test and release?

Run test files separately with isolated storage; see [Testing](../dev/testing.md). Package versions come from `hierachain/config/version.py`; see [Release process](../dev/release-process.md).
