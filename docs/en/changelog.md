---
title: "Changelog"
description: "Main change log for HieraChain and accompanying documentation."
icon: material/history
---

# Changelog

## Unreleased

??? note "Improvements (89)"

    * 2026-07-18

        * **Testing**: Added JUnit XML reporting support (`--junitxml`) to Docker, Podman, and Kubernetes stress execution scripts.
        * **Dependencies**: Cleaned up project dependencies by removing unused packages (`pip`, `vulture`, `wheel`) from dev environments.
        * **Storage**: Tuned IPFS connection pooling parameters (`max_keepalive_connections=50`, `max_connections=150`) to accelerate concurrent block storage.
        * **Stress**: Added dynamic configuration support via environment variables in `test_tsunami_flood.py` and implemented resilient HTTP adapter retries on 502/503/504 errors.
        * **Core**: Resolved critical indexing race conditions in block creation within lock constraints and aligned initial index references.
        * **Database**: Optimized SQLite adapter by setting database connection timeout to 30.0 seconds to prevent write-lock exceptions under high parallel load.

    * 2026-07-17

        * **Performance**: Replaced `json` with `orjson` across the entire codebase — security, risk_management, network, monitoring, privacy, config, CLI, API, and hierachain modules — for faster serialization/deserialization.
        * **Core**: Added optimized data payload recovery for blocks with direct `data` column parsing when available.
        * **Security**: Optimized signature verification with configurable thread pool (CPU count) and extracted `_get_verify_key` helper for public key decoding.
        * **Testing**: Extended sleep duration in `test_repro_determinism` from 0.5s to 1.5s for full service shutdown reliability.

    * 2026-07-16

        * **Testing**: Fixed false positive in term censorship test — skipped docstring examples explaining regex word-boundary matching.
        * **Documentation**: Added PR description template for merging v0.0.x into main.
        * **Changelog**: Updated unreleased section with recent developments.

    * 2026-07-12

        * **Network**: Fixed seed node public key decoding with special handling for `$$` delimiter characters.

    * 2026-07-11

        * **Docker**: Added `DISABLE_WIREGUARD` option to skip WireGuard interface initialization.

    * 2026-07-10

        * **Documentation**: Updated docs for clarity and project structure; enhanced PR template.

    * 2026-07-09

        * **Risk Management**: Improved database connection handling in audit logger.
        * **Policy**: Fixed Null value evaluation in Arrow `StructArray`.
        * **Testing**: Added integration test for cryptocurrency term censorship; added database audit storage integrity tests.

    * 2026-07-08

        * **CI**: Refined issue templates for clarity; added pull request template.

    * 2026-07-07

        * **Infrastructure**: Updated K8s/Podman setup scripts to use `uv` for Python commands.
        * **Stress**: Tuned poison pill acceptance rate threshold for better reliability.

    * 2026-07-06

        * **Stress Testing**: Implemented full network stress testing framework (bandwidth, latency, packet loss simulation); added resource monitoring and alerting framework.
        * **WebSocket**: Enhanced load test reliability.

    * 2026-07-05

        * **Database**: Enhanced SQL adapter with metadata and merkle root support.
        * **API**: Renamed API version tags for clarity (`v1` → `ledger`, `v2` → `business`, `v3` → `admin`); updated security testing scripts and health check endpoints accordingly.
        * **Documentation**: Reorganized API version docs for improved clarity.
        * **Demo**: Fixed metadata filename in IPFS demo; updated version attribute/import paths.

    * 2026-07-04

        * **API**: Restructured API modules for better security and maintainability; uses background tasks for async security event recording.
        * **Monitoring**: Implemented comprehensive performance monitoring module; added alert system with anomaly detection and notification.
        * **Risk Management**: Implemented `DatabaseAuditStorage` for persistent audit logging.
        * **Refactoring**: Removed deadlock detector and related tests; removed `sql_backend` references; reorganized version management.

    * 2026-07-02

        * **Storage Migration**: Replaced `SqlStorageBackend` with `SQLiteAdapter`; deleted legacy storage module.
        * **Database**: Added chain state table for quick state lookups; added blockchain data storage and retrieval functions.

    * 2026-07-01

        * **API Routing**: Major refactoring of API routing structure and module names; optimized middleware and WebSocket manager.
        * **Domains**: Refactored event extraction logic and transaction management; removed generic-level re-export shim.
        * **Testing**: Updated import paths and test files for new API structure.

    * 2026-06-30

        * **Dead Code Removal**: Removed unused modules across core (performance, parallel_engine), storage (`ChainModel`), network (message encryption exception classes), error_mitigation, domains (entity reporting, compliance), consensus, API, and adapters.
        * **State**: Removed `apply_event_list` function from world state.
        * **Event Ledger**: Reconstructed event data structure and storage logic.

    * 2026-06-24

        * **Dependencies**: Added `vulture` for dead code detection; removed `tox` configuration (migrated to `uv`).

    * 2026-06-23

        * **Hierarchical**: Modularized `MainChain` (proof + registry), `SubChain` (rehydration logic), `Rebalancer` (event extraction), `HierarchyManager` (cross-level sync init), K8s namespace manager; added `compliance_checker`.
        * **Consensus**: Improved signature extraction and verification logic.
        * **Monitoring/Alert**: Modularized into separate packages with shared types.
        * **ERP**: Modularized integration components for better maintainability.
        * **Security**: Improved API key storage and caching management.
        * **Events**: Moved domain event classes with factory functions; moved metrics and transaction manager to separate modules.
        * **Core**: Improved event queries and type handling.

    * 2026-06-22

        * **BFT Consensus**: Restructured into modular components (engine, dispatcher, view_change).
        * **Ordering**: Restructured batch processing and validation logic.
        * **Cluster**: Extracted node validation and authentication helpers.
        * **Redis**: Restructured adapter into manager classes with delegate operations.
        * **Security**: Extracted production security checks to helper function.
        * **API**: Extracted chain block lookup and creation helpers.
        * **WebSocket**: Added explicit `None` type annotations for optional parameters.
        * **Schemas**: Optimized payload depth validation to use stack traversal.

    * 2026-06-21

        * **Performance**: Replaced `json` with `orjson` across database layer for faster serialization.
        * **Journal**: Added asynchronous background writing for event logging.
        * **Security**: Optimized batch signature verification and proof serialization.

    * 2026-06-20

        * **Consensus**: Optimized batch signature verification; delegated crypto term validation to core utility.

    * 2026-06-19

        * **Domains**: Reorganized package structure; migrated generic modules; removed `generic/` layer.
        * **Hierarchical**: Implemented `HierarchyManager` for chain coordination; restructured sub-chain proof handling.
        * **Core**: Improved block event processing and merkle tree handling.
        * **Consensus**: Reorganized BFT consensus; updated PoA and PoF classes.
        * **Security**: Removed deprecated certificate and backup modules; simplified imports.
        * **Storage**: Removed memory storage and world state modules.
        * **State**: Added `WorldState` class for entity state management.
        * **Error Mitigation**: Removed deprecated rollback and recovery modules.
        * **Integration**: Removed `ArrowClient` and related types.
        * **Network**: Removed `NetworkClientSync` synchronous wrapper.
        * **Database**: Added `RedisStorageAdapter` for Redis blockchain storage.
        * **Config**: Removed unused cache and parallel processing settings.
        * **CLI**: Fixed import path for `DomainChain`.
        * **Version**: Simplified version module; removed unused functions.
        * **Dependencies**: Added `orjson 3.11.9`.

    * 2026-06-17

        * **SDK**: Restructured into sync and async clients with shared types and exceptions.
        * **Security**: Modularized certificate and key backup management.
        * **Risk Management**: Restructured and optimized modules.

    * 2026-06-16

        * **Core Cache**: Replaced monolithic `caching.py` with modular `Cache` and `CacheManager` components.
        * **BFT**: Consolidated BFT helpers into single module.
        * **Cluster**: Moved data types to separate modules (lockdown_types, cross_level_sync_types).
        * **Monitoring**: Unified alert and performance types into shared module.
        * **Integration**: Moved error and sync classes to types module.
        * **Hierarchical**: Centralized shared types into new `types.py` module.
        * **Error Mitigation**: Added comprehensive error mitigation modules (consensus_validator, resource_validator, network_recovery, auto_scaler, backup_recovery).

    * 2026-06-15

        * **API Restructuring**: Split monolithic `v1/endpoints.py` into modular components; modularized `v2/endpoints.py`; fixed `v3` import paths.
        * **GraphQL**: Restructured schema and resolvers for better organization.
        * **Database**: Added base SQL adapter and integrated into `SQLiteAdapter`.
        * **Server**: Modularized middleware and GraphQL handler; optimized server setup; modularized blockchain explorer into components.

---

## v0.0.6 (2026-07-15)

This release focuses on security hardening of the logging subsystem, simplification of the core blockchain and hierarchical layers, and further consensus hardening with proper error handling.

??? note "Improvements (6)"

    * **Secure Logging**: Added regex-based redaction of sensitive keys and tokens in `hierachain/security/` — sensitive values are replaced with `'***'` to prevent credential leakage. Introduced `_SEVERITY_MAP` for consistent security event logging, replacing direct log level methods with `logger.log()` — reducing duplication across all logging call sites.
    * **Core Blockchain Refactoring**: Added `_rebuild_event_indexes` to reset and rebuild event indexes after block loading — ensuring index consistency across restarts. Changed hash mismatch from silent correction to raising an exception — no more hiding potential data corruption. Replaced direct dictionary access with `block.to_event_list()` for cleaner event filtering.
    * **Consensus Hardening**: Enhanced `_contains_forbidden_terms` with regex word-boundary matching to eliminate false positives. Removed fallback random signature generation — signing now fails cleanly with an error message when the private key is missing. `ProofOfFederation` auto-generates key pairs for validators, exposes `public_key` property, added `block_hash` to consensus metadata. `_verify_block_quorum` now accepts optional `signer_id` to avoid redundant event re-scanning.
    * **Hierarchical Layer Simplification**: Removed temporary entity index mapping, local chain clear, event statistics reset in sub-chain rehydration. Removed redundant event addition to `Blockchain.pending_events`. Streamlined `_recover_pending_events_from_journal` to count uncommitted events only, moving event reconstruction to `OrderingRecovery`.
    * **Testing & Benchmark**: Enhanced ZK Proof-of-Federation test with real keypair, real signatures, and pre-consensus block validation. Updated storage benchmark using `Block` class from `hierachain.core`, renamed `event_type` to `event`. Added helper function for `ProofOfFederation` instantiation with signing key.

??? warning "Fix (1)"

    * **Logger Test Alignment**: Updated test assertions to match new logger method signatures (`mock_info` → `mock_log`, `call_args` indexing adjusted).

---

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
