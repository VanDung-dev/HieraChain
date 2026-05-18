---
title: "Changelog"
description: "Main change log for HieraChain and accompanying documentation."
icon: material/history
---

# Changelog

## v0.0.3 (2026-05-02)

This release focuses on production readiness through comprehensive type safety improvements in `hierachain/`, Kubernetes StatefulSet deployment, robust stress testing infrastructure, and enhanced security validation.

??? note "Improvements (6)"

    * **Full Mypy Compliance**: Resolved static typing warnings across consensus, API, security, network, monitoring, error mitigation, storage, adapters, hierarchical, domains, core and cluster modules.
    * **Ed25519 Signature Validation**: Enforced strict 64-byte length for Ed25519 signatures to prevent validation bypass.
    * **JSON Canonicalization**: Implemented robust JSON canonicalization for signature verification to ensure consistent cryptographic operations.
    * **StatefulSet Migration**: Migrated from Deployment to StatefulSet for stable node deployment with persistent identity.
    * **Security**: Added payload limit middleware, 24h timestamp validation, default API key prevention in production, refactored HMAC lockdown protocol.
    * **Build & Packaging**: Migrated dependency management to uv, pinned dependency versions, added uv.lock.

??? warning "Fix (1)"

    * **Testing & Stability**: Limited message log in BFT consensus, improved stress test client, fixed bare except clauses in integration tests, improved IPFS connection handling.

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

??? warning "Fix (3)"

    * **Consensus & Ordering Stability**:

        * Resolved critical race condition in block commit and pending event handling in `OrderingService`.
        * Ensured lockdown and resume operations are atomic to prevent inconsistent state during maintenance.
        * Prevented silent data loss during transaction journal recovery with proper validation.
        * Improved state recovery logic with config validation and modularized recovery from transaction journal.

    * **Core & Hierarchical Chain**:

        * Fixed race condition in hierarchical chain management and added graceful shutdown procedures.

    * **Build & Packaging**:

        * Embedded config template into Python module to fix missing `.env.HRC.example` file when installing via pip.

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
        * Improved CI/CD reliability with matrix testing and flaky test handling.
