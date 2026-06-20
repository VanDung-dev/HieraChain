---
title: "Changelog"
description: "Main change log for HieraChain and accompanying documentation."
icon: material/history
---

# Changelog

## v0.0.5 (2026-06-20)

This release focuses on core `hierachain/` package improvements, including replacing `ipfshttpclient` with `httpx` for Kubo RPC, idempotent sub-chain creation, chain integrity hardening, block persistence, and safe edge-case handling.

??? note "Improvements (6)"

    * **Kubo RPC Migration**: Replaced `ipfshttpclient` with `httpx` in `hierachain/api/storage/ipfs_client.py`, executing IPFS operations directly via Kubo HTTP RPC API. Added `_parse_multiaddr` helper for host/port extraction from multiaddress strings. Refactored core operations (upload, download, pin, unpin, list_pins, stats) to use `httpx.Client` POST requests. Removed `_IPFSClientContext` wrapper class.
    * **Idempotent Sub-Chain Creation**: API v1 (`hierachain/api/v1/endpoints.py`) checks for existing sub-chain before creation, returns `201 Created` with `"already_exists"` audit trail for duplicates. Returns `409 Conflict` when `manager.add_sub_chain` raises `ValueError` on duplicate.
    * **Chain Integrity Hardening**: Added `_verify_chain_links()` in `hierachain/consensus/ordering/storage.py` to validate `previous_hash` chain of blocks. `_block_from_dict` raises `ValueError` on computed hash mismatch instead of merely logging an error.
    * **Event Enrichment & Block Persistence**: Ordering service (`hierachain/consensus/ordering/service.py`) injects `event_id` into `event_data` payload before creating pending events. Recovery (`recovery.py`) prioritizes enriched `event_data` over calculated fallback. Sub-chain finalize (`hierachain/hierarchical/sub_chain.py`) persists blocks via storage handler, ensuring rehydration retains consensus events.
    * **Block Overwrite**: `hierachain/storage/sql_backend.py` — `save_block` queries for existing blocks by `index`/`chain_name`, deletes and replaces them instead of silently handling `UNIQUE constraint` violations.
    * **Zero Children Safeguard**: Rebalancer (`hierachain/hierarchical/rebalancer.py`) safely returns `0` when `num_children <= 0`, preventing modulo-by-zero errors.

??? warning "Fix (1)"

    * **Integrity Check Locking**: Moved post-rehydration chain integrity validation outside the lock in `hierachain/hierarchical/sub_chain.py`. Downgraded mismatch log from error to warning to account for pending consumer thread blocks.

---

## v0.0.4 (2026-05-25)

This release focuses on Node Identity with Ed25519/Curve25519 keypairs, ZeroMQ CURVE encryption for P2P, API v3 secure event submission, Ed25519 signing for Proof of Federation, BFT timestamp validation against replay attacks, and comprehensive security hardening within `hierachain/`.

??? note "Improvements (4)"

    * **Node Identity & P2P Networking**: Introduced `NodeIdentity` in `hierachain/security/identity_loader.py`, ZeroMQ CURVE encryption in `NetworkClient`, `send_direct`/`broadcast` methods, ping-pong heartbeat. Propagated node identity through `HierarchyManager`, `DomainChain`, `OrderingService`, and BFT consensus.
    * **API v3 & Cryptographic Signatures**: New `POST /api/v3/chains/{chain_name}/secure-events` endpoint with Ed25519 signature verification, 1MB payload limit, and max depth 10. Added `sender`/`signature` fields to v1 event schemas with strict hex validation.
    * **Consensus Hardening**: Ed25519 signing for Proof of Federation (`_create_federation_signature`, `_verify_block_quorum`), 30-second BFT timestamp drift check against replay attacks, block hash verification on reconstruction, configurable `block_interval` via `HRC_BLOCK_INTERVAL`.
    * **Security**: Production ZK proof rejection (test environment bypass), HMAC constant-time comparison (`hmac.compare_digest`), `threading.RLock` in LockdownProtocol, PBKDF2 increased to 310,000 iterations, `AdvancedCache` with TTL/LRU for `KeyManager`.

??? warning "Fix (2)"

    * **Consensus & Storage**: Fixed block signature verification and auto key generation in PoA, corrected default return value in BFT handler from `True` to `False`, added 64-char SHA-256 proof_hash validation, chain integrity checks after deserialization, added `creator_id`/`signature` columns to block DB model.
    * **API & SDK**: Updated SDK default base URL from 8000 to 2661, sub-chain name regex validation, thread-safe `RateLimiter`, CID/nonce validation in IPFS client.

---

## v0.0.3 (2026-05-02)

This release focuses on comprehensive type safety improvements across `hierachain/`, achieving full Mypy compliance, strict Ed25519 64-byte signature validation, JSON canonicalization for deterministic verification, HMAC-based lockdown protocol, payload limit middleware, and 24-hour timestamp validation.

??? note "Improvements (4)"

    * **Full Mypy Compliance**: Resolved static typing warnings across all modules — consensus, API, security, network, monitoring, error mitigation, storage, adapters, hierarchical, domains, core and cluster.
    * **Ed25519 Signature Validation**: Enforced strict 64-byte length for Ed25519 signatures in `verify_signature_standalone` to prevent validation bypass.
    * **JSON Canonicalization**: Implemented robust `get_canonical_bytes` with recursive dict sorting, Unicode NFC normalization, and consistent float formatting for deterministic signature verification.
    * **Security**: Added `PayloadLimitMiddleware` rejecting POST/PUT/PATCH over 1MB, 24h proof timestamp consistency validation, default API key prevention in production (`RuntimeError`), refactored HMAC lockdown protocol (`hmac.new` SHA256).

??? warning "Fix (1)"

    * **BFT & Validation**: Limited BFT message log to 10,000 entries preventing unbounded memory growth, improved IPFS connection handling (`_ensure_connected` with proper None checks), fixed bare except clauses, enforced `\b` word-boundary matching for cryptocurrency term validation.

---

## v0.0.2 (2026-04-04)

This release focuses on enhanced security, system observability, and important stability improvements for the core `hierachain/` package, addressing real-world issues discovered during testing and evaluation.

??? note "Improvements (5)"

    * **Unified Secret & Credential Management**:

        * Introduced unified `SecretManager` in `config` for secure credential management with multiple backend support.
        * Prevented accidental secret leakage in logs by masking secret names and backend identifiers.
        * Prevented automatic master key generation in production to require explicit key provisioning.

    * **Security & Policy**:

        * Added persistent storage for brute force lockouts and proactive rejection of dangerous input patterns in policy engine.
        * Enhanced directory creation checks to prevent path traversal attacks in SubChain SQLite database paths.
        * Added dedicated security module for GraphQL endpoint with input validation and access control.

    * **Observability & Monitoring**:

        * Integrated Prometheus metrics collection for real-time monitoring of API latency, block throughput, and consensus health.
        * Added JSON logging support for better integration with log aggregation systems like ELK and Loki.
        * Added simple alert methods and global instance manager for proactive event notification.
        * Enhanced API rate limiting with Redis backend for distributed deployments.

    * **Core & Hierarchical Chain Improvements**:

        * Implemented deadlock detection with timeout and recovery mechanisms in lock management.
        * Escalated missing ZK proof severity to critical and integrated automatic alert triggering.
        * Improved proof submission robustness and shutdown handling in hierarchical chains.
        * Added input validation for `ChannelLedger.add_event` to prevent malformed events.

    * **Developer Tools & CLI**:

        * Added dedicated CLI commands for key generation, backup, and recovery (`python -m hierachain key ...`).
        * Added endpoint to fetch specific blocks by index or hash for targeted audit.
        * Updated SDK client for full multi-chain API v3 support.
        * Synchronized block schema with event schema for consistent data structure.

??? warning "Fix (2)"

    * **Consensus & Ordering Stability**:

        * Resolved critical race condition in block commit and pending event handling in `OrderingService`.
        * Ensured lockdown and resume operations are atomic to prevent inconsistent state during maintenance.
        * Prevented silent data loss during transaction journal recovery with proper validation.
        * Improved state recovery logic with config validation and modularized recovery from transaction journal.

    * **Core & Hierarchical Chain**:

        * Fixed race condition in hierarchical chain management and added graceful shutdown procedures.

---

## v0.0.1 (2026-03-22)

This release marks the completion of HieraChain's initial architectural direction, focusing on consolidating core components into a unified prototype framework.

??? note "Improvements (4)"

    * **IPFS Storage Integration**: Support for off-chain data storage with AES-256-GCM encryption and CID identifiers across all API interfaces (REST, GraphQL, WebSocket).
    * **Performance & Scalability Optimization**:

        * Parallel block processing in `OrderingService`.
        * Caching for certificate and permission validation.
        * Worker pool optimization (75% CPU) and multi-threading support for SQLite.

    * **Developer Tools**: Launched `BlockchainExplorer` dashboard and detailed technical documentation system.
    * **Security & Integrity**: 

        * Merkle Root support in block header and storage.
        * Ensured hash consistency and thread-safety for core components.
        * Standardized security logging with `SecureLogger`.

??? warning "Fix (1)"

    * **Stability & QA**: 

        * Fixed Chain Rehydration bug for correct state restoration after restart.
