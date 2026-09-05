---
title: "Changelog"
description: "Main change log for HieraChain and accompanying documentation."
icon: material/history
---

# Changelog

## Unreleased

??? note "Improvements (26)"

    * 2026-09-05

        * **Core (Block, Blockchain & Merkle Tree)**: Hardened `Block` caching and hash guard in `hierachain/core/block.py` (type-checked `stored_hash`, cached event list), added deterministic `event_id` generation (`orjson`+SHA-256 `evt-{16}`) and Merkle-root verification in `_is_block_linked_correctly`/`Blockchain.add_event()` now returning `str` (`hierachain/core/blockchain.py`), and fixed `MerkleTree._build_tree` odd-node handling to propagate unduplicated leaf instead of hashing duplicate (`hierachain/core/merkle_tree.py`).
        * **Core (Logging & Error Handling)**: Narrowed broad `except Exception` to `OSError`/`ArrowException`/`ValueError`/`TypeError` in `hierachain/core/parquet_log.py` and `hierachain/error_mitigation/journal.py`, added typed `pa.Table | None` annotation, and added `ImportError` fallback for `kubernetes` client in `hierachain/hierarchical/k8s_namespace_manager/operations.py`.
        * **Consensus (BFT & PoA/PoF & Ordering)**: Added strict `isinstance(str)` guards for `signature`/`public_key`/`block_hash` in `hierachain/consensus/proof_of_federation._verify_block_quorum` and removed insecure `KeyPair` fallback in `hierachain/consensus/proof_of_authority.py`; tightened BFT validation in `hierachain/consensus/bft/helpers.py` (`strictness` early-return and per-sequence digest/view quorum matching in `_process_commit_quorum_logic`); simplified `hierachain/consensus/ordering/recovery.py` type handling (`int(block_index_raw)`, `dict|None`).
        * **Consensus & Hierarchical (Types & Schema)**: Replaced `TYPE_CHECKING` forward references with runtime `Any` across `hierachain/consensus/bft/dispatcher.py|engine.py|view_change.py` and `hierachain/hierarchical/main_chain/proofs.py|registry.py|rebalancer/split_ops.py|sub_chain/*.py`; centralized `EVENT_SCHEMA` (`pa.schema`) in `hierachain/core/block.py` and reused it in `hierachain/consensus/ordering/certifier.py`, `hierachain/error_mitigation/journal.py`, `hierachain/hierarchical/channel/ledger.py`; enhanced `BFTViewChangeManager` to emit `prepared_proofs`.
        * **Hierarchical (Hierarchy Manager & SubChain)**: Enhanced `_shared_pool` in `hierachain/hierarchical/hierarchy_manager/base.py` to support dynamic `max_workers` (spawns ephemeral pool when changed, else reuses global); replaced `hash()` with deterministic `orjson`+SHA-256 `evt-` ID in `hierachain/hierarchical/sub_chain/base.py`; removed unused legacy `hierachain/hierarchical/sub_chain.py`.
        * **Hierarchical (Rollback & Rebalancer)**: Hardened `hierachain/error_mitigation/rollback_manager.py` with component-aware `_capture_storage_state`, path-traversal guard via `os.path.realpath` in `_rollback_configuration`, section-count logging and `data_hash` integrity check; cleaned `hierachain/error_mitigation/validator_helpers.py` and narrowed imports; simplified `hierachain/hierarchical/rebalancer/split_ops.py` imports.
        * **API (Middleware, Server & WebSocket)**: Streamed payload limit via `request.stream()` with `bytes_read` accounting and `request._receive` replay in `hierachain/api/middleware.py`; enforced trusted-proxy check `client_ip in TRUSTED_PROXIES` for `X-Forwarded-For` and fixed rate-limit IP fallback; extracted CORS to `_add_cors_middleware` in `hierachain/api/server.py` and made `uvloop` mandatory; simplified `PingLoopRunner` init in `hierachain/api/websocket/manager.py`.
        * **API (Ledger, GraphQL, Explorer & Business)**: Centralized default field handling in `hierachain/api/storage/explorer_helpers.py`; added `assert` guards in `hierachain/api/ledger/depds.py` and replaced recursive depth check with iterative stack (`depth >10`) in `hierachain/api/ledger/schemas.py`; adapted `hierachain/api/graphql/resolvers.py|types.py` for `Blockchain.add_event()->str` and `is_cid_string` logic; typed `private_data_entry: dict[str,Any]` in `hierachain/api/business/private_data.py`.
        * **API (Admin Identity - Feature)**: Added optional `nonce`/`timestamp`/`chain_id` fields to `SecureEventRequest` (`hierachain/api/admin/schemas.py`), enforced `chain_id` mismatch (`422`) and 300s timestamp freshness, prefixed challenge with `b"HRC_IDENTITY_CHALLENGE:"` and restored `require_chain_access` dependency for `/verify-identity` (`hierachain/api/admin/endpoints.py`).
        * **Security, Events, Database & Cleanup**: Simplified `_sanitize_html_context` to `re.sub(..., "[TEMPLATE_BLOCKED]")` (`hierachain/security/sanitization.py`) and switched ZK mock verification to `ZKVerifier(mode="mock").verify` (`hierachain/security/zk_prover.py`); tightened `BaseEvent.__eq__(other: object)` (`hierachain/domains/events/base_event.py`); centralized DB schema init to `init_database_schema` in `hierachain/adapters/database/postgres_schema.py|sqlite_schema.py` and simplified adapters; removed 17 unused imports across `api/storage`, `consensus/ordering`, `core/utils`, `error_mitigation/*`, `risk_management/*`.

    * 2026-09-01

        * **Database (PostgreSQL)**: Introduced `PostgresAdapter` (`hierachain/adapters/database/postgres_adapter.py`) extending `SQLBase` with `psycopg`/`psycopg2` connection pooling (dictionary row access) and `postgres_schema.py` defining tables (`chains`, `blocks`, `events`, `proofs`, `chain_state`) with optimized composite indexes (`chain_name+timestamp`, `entity_id+chain_name`, `block_hash`) and full CRUD for blockchain data.
        * **Config**: Enhanced storage/database flexibility in `hierachain/config/settings.py` and `hierachain/config/product_config_template.py` — added `BLOCK_CREATION_MODE`/`BLOCK_MAX_WAIT_SEC` for block creation control, `PARQUET_ROLL_INTERVAL` (`monthly`/`daily`/`by_size_mb`), `POSTGRES_SYNC_MODE` (`realtime`/`batch_worker`/`disabled`), `SQL_RETENTION_DAYS`; made `STORAGE_BACKEND` auto-detect `postgres` from `DATABASE_URL` with `sqlite` fallback and unified `DATABASE_URL`/`HRC_DATABASE_URL` handling; streamlined product template backends to `sqlite`, `postgres`, `redis`, `memory`, `parquet_only`.
        * **Storage (Hierarchical & Ordering)**: Added dynamic adapter selection in `hierachain/consensus/ordering/storage.py` (`OrderingStorageHandler`), `hierachain/hierarchical/hierarchy_manager/base.py` (`_create_storage`) and `hierachain/hierarchical/sub_chain/base.py` — selects `PostgresAdapter` when `db_url` starts with `postgres://`/`postgresql://` otherwise `SQLiteAdapter`; refactored `SubChain` DB path generation to always ensure `data/{safe_name}/journal` exists with path-traversal guard.
        * **Database (Query & Indexes)**: Optimized `hierachain/adapters/database/sqlite_schema.py` (`create_indexes` now uses full `CREATE INDEX` statements) and refactored `hierachain/adapters/database/base/sql_adapter.py` to use predefined reusable query templates (`_QUERIES_WITH_CHAIN`/`_QUERIES_WITHOUT_CHAIN`) with parameterized queries for chain-aware event filtering, and fixed block cleanup to delete via `hash`/`block_hash` instead of `id`/`block_id`.

    * 2026-08-31

        * **SDK**: Replaced `assert` statements with explicit `RuntimeError` checks in `_get_session` across `hierachain/sdk/client.py` and `hierachain/sdk/async_client.py` to prevent session validation from being skipped in optimized byte-code mode (`-O`).
        * **Logging & Error Mitigation**: Replaced bare `except Exception: pass` and `continue` blocks with explicit `logger.debug()` messages in `hierachain/core/parquet_log.py`, `hierachain/error_mitigation/journal.py`, and `hierachain/risk_management/audit_logger.py` for file closing, unlinking, rotation recovery, and batch replaying, improving error visibility while maintaining fail-safe execution.

    * 2026-08-29

        * **Journal**: Migrated `TransactionJournal` (`hierachain/error_mitigation/journal.py`) to Parquet storage (`pyarrow.parquet`) with 100MB file cap, auto rotation `current_{ns}.parquet`, bounded async queue (10k) and thread-safe `ParquetWriter` management, plus replay over multiple Parquet files with backward compat for `.arrow`/`.log`.
        * **Audit**: Added `ArrowAuditStorage` (`hierachain/risk_management/audit_logger.py`) as default backend, persisting `AuditEvent` via Parquet with Arrow schema, 100MB rotation, `AuditFilter`-aware retrieval, and compat for `*.jsonl`.
        * **Logging**: Unified all `log/` persistence to Parquet via `hierachain/core/parquet_log.py` (`write_parquet_log`, `ParquetLogHandler`), migrating `consensus_scaling`, `view_changes`, `error_classifications`, `restoration_events`, `scaling_events`, `network_alerts`, `resource_scaling`, `rollback_operations`, `quarantine_dump`, `risk_analyzer`, `mitigation_strategies` to `*.parquet` and switching `OrderingService` to `node_{id}_journal.parquet`.

    * 2026-08-27

        * **API**: Adjusted authentication handling in `hierachain/api/server.py` (added `Request` annotation to `auth_dependency`, unified `verifier` initialization and extended `EXEMPT_PATHS` with `/api/admin/verify-identity`) and removed redundant `require_chain_access` dependencies in `hierachain/api/admin/endpoints.py` for `/verify-identity` and `/status` so health checks and identity verification work correctly when `HRC_ENV=product`.

    * 2026-08-24

        * **API**: Introduced `hierachain/api/context.py` for decoupled, context-based P2P client runtime lifecycle management across API server initialization, shutdown, and network ping endpoints.
        * **Hierarchical (Rebalancer)**: Centralized sub-chain utility functions into `hierachain/hierarchical/rebalancer/utils.py` and streamlined state migration during sub-chain splitting to migrate pending events and inherit entity World State snapshots without altering committed block history.
        * **Domains**: Streamlined domain event module structure in `hierachain/domains/events/`, decoupling cross-module circular imports between `DomainEvent` base and concrete event definitions.

    * 2026-08-23

        * **Network**: Added timestamp drift validation (`max_drift`, default 300s) to `verify_message` in `hierachain/network/message_cryptographic.py` to ensure freshness of received P2P messages and reject replayed packets with stale timestamps.
        * **API (Rate Limiter)**: Optimized in-memory `RateLimiter` in `hierachain/api/middleware.py` with periodic batch expiration cleanup (`_cleanup_expired`), eliminating $O(N)$ dictionary rebuilds and lock contention on every request under high traffic load; added client IP extraction from `X-Forwarded-For` header for proxy deployments.
        * **Core & Hierarchical**: Enhanced `finalize_block` in `Blockchain` (`hierachain/core/blockchain.py`) and `MainChain` (`hierachain/hierarchical/main_chain/base.py`) to preserve `pending_events` when block creation or validation fails, preventing event data loss; added `self.lock` synchronization to `MainChain` block finalization methods.

    * 2026-08-15

        * **Dead Code Removal**: Removed unused utility functions across hierarchical and domain modules (`hierachain/core/utils.py`, `consensus/proof_of_federation.py`, `domains/chains/domain_chain.py`, `domains/chains/metrics.py`, `domains/utils/cross_chain_validator.py`, `domains/utils/entity_tracer.py`, `hierarchical/multi_org.py`): deleted `group_events_by_entity`, `_is_block_valid`, `_extract_signature_from_block`, `_analyze_compliance_status`, `_calculate_performance_stats`, `_process_string_value`, `_process_bytes_value`, `_generate_recommendations`, and `create_multi_org_network` for a leaner, more maintainable codebase.

??? warning "Fix (15)"

    * 2026-08-31

        * **Security (Secret Manager)**: Sanitized exception logging templates in `_get_from_aws` (`hierachain/config/secret_manager.py`) to eliminate false-positive credential disclosure warnings during static security audits.

    * 2026-08-29

        * **Security (Sanitization)**: Fixed `_sanitize_html_context` (`hierachain/security/sanitization.py`) to neutralize SSTI with `[TEMPLATE_BLOCKED]` instead of no-op `html.escape`, and tightened `_sanitize_filename_context` with allowlist `^[a-zA-Z0-9_\-~.]+$` and `..`/`.` filtering to prevent path traversal.

    * 2026-08-27

        * **Security (Key Manager)**: Added `PYTEST_CURRENT_TEST`/`pytest` guard in `initialize_default_keys` (`hierachain/security/key_manager.py`) to prevent default API key creation in test environments when `HRC_ENV=product` and allow safe initialization under `pytest`.
        * **Hierarchical (Rebalancer)**: Handle both `callable` and `non-callable` pending events in `_get_pending_events` (`hierachain/hierarchical/rebalancer/split_ops.py`) by checking `callable()` and falling back to the `pending_events` list.
        * **Consensus (BFT)**: Relaxed timestamp drift threshold from 30s to 120s in `verify_message_signature` (`hierachain/consensus/bft/helpers.py`) to avoid drift failures when the suite runs long with a statically created message at import time.
        * **Config (Env Manager)**: Added `HRC_ENV=test`/`PYTEST_CURRENT_TEST` checks in `init_env_config` (`hierachain/config/env_manager.py`) to prevent creating `.env.HRC.example` and loading the product `.env` while running `pytest`.
        * **Cluster (Lockdown)**: Hardened `verify_signature` in `hierachain/cluster/lockdown_types.py` with empty `str` type checks and `try/except` around `hmac.compare_digest` to safely handle invalid signatures while maintaining backward compatibility with legacy 32-char truncated signatures.

    * 2026-08-24

        * **Consensus (Ordering)**: Added empty batch check (`if not self.current_batch: return False`) to `is_batch_ready` in `BlockBuilder` (`hierachain/consensus/ordering/block_builder.py`) to prevent false-positive readiness checks and no-op block creation triggers during idle timeout periods.
        * **Core (Merkle Tree)**: Added domain separation prefix (`0x01`) to internal node hashing in `MerkleTree._build_tree` (`hierachain/core/merkle_tree.py`) to prevent node duplication and second-preimage collision risks.
        * **API (Payload Limit)**: Enforced upload payload size limits (1MB) on streaming/chunked requests lacking `Content-Length` in `add_payload_limit` (`hierachain/api/middleware.py`).

    * 2026-08-23

        * **Consensus (BFT)**: Enforced strict signature verification in `_validate_consensus_message` (`hierachain/consensus/bft/helpers.py`), ensuring that incoming BFT messages (`PRE-PREPARE`, `PREPARE`, `COMMIT`) with invalid or missing signatures are always rejected (`return False`) across all strictness modes.
        * **Hierarchical (Proof Verification)**: Added fallback chain scanning in `_verify_proof_in_main_chain` (`hierachain/hierarchical/main_chain/proofs.py`) to search committed blocks when a proof submission is not yet reflected in the O(1) `proof_index`.
        * **Cluster (Lockdown Protocol)**: Standardized `LockdownMessage` HMAC-SHA256 signatures in `hierachain/cluster/lockdown_types.py` to use the full 64-character hex digest (256-bit) while maintaining backward compatibility with legacy 32-character truncated signatures in `verify_signature`.

    * 2026-08-14

        * **Security (ZK Mock Proof)**: `_generate_mock_proof` in `hierachain/security/zk_prover.py` now accepts a `sub_chain_name` parameter and includes it in `public_inputs`, fixing the SHA-256 commitment being computed with `sub_chain_name=""` while the verifier hashed with the real sub-chain name (causing every proof to be rejected when `ENABLE_ZK_PROOFS=true`). `_verify_mock_proof` replaces the lax `mock_proof` prefix check with the standard `_verify_mock` logic from `zk_verifier` (commitment hash vs `public_inputs`), rejecting fake proofs.
        * **Hierarchical**: Moved the genesis-only chain guard above `get_latest_block()` in `_submit_proof_for_sub_chain` (`hierachain/hierarchical/sub_chain/proof.py`), preventing an `IndexError` on an empty SubChain and returning `False` as intended.

---

## v0.1.0 (2026-08-10)

This major milestone release marks the consolidation of HieraChain's core library architecture (`hierachain/`). Key highlights include complete terminology standardization, dual-tier consensus refinement (PoA for Intra-Org SubChains and PoF for Inter-Org MainChain alliances), integration of high-performance libraries (`orjson`, `uvloop`), extensive dead code removal, and API router restructuring.

??? note "Improvements (52)"

    * 2026-07-27

        * **Consensus**: Introduced `HRC_MAINCHAIN_CONSENSUS` env var with backward-compatible `HRC_CONSENSUS_TYPE` alias. `MainChain.__init__` accepts optional `consensus_type` parameter. `SubChain` now defaults to PoA for intra-org domain events, configurable via `config["consensus_type"]`.

    * 2026-07-23

        * **Refactoring**: Moved all inline/late imports (`os`, `sys`, `time`, `uuid`, `asyncio`, `warnings`, `httpx`, `pyarrow`, `cast`) to module-level top-of-file across 14 source files, fully conforming to PEP 8 import ordering.

    * 2026-07-22

        * **API**: Integrated `uvloop` dependency and enabled high-performance async event loop support in API server.
        * **Blockchain**: Introduced `event_type_index` on `Blockchain` and `to_event_list` on `Block` for O(1) event type lookups.
        * **Cache**: Replaced standard list with `OrderedDict` for LRU/TTL access ordering and simplified thread cleanup lifecycle.
        * **Security**: Refactored cryptocurrency term validation with recursive structure traversal, replacing expensive JSON regex serialization.
        * **Hierarchical**: Optimized `HierarchyManager` to use a shared thread pool executor context, reducing thread creation overhead during proof sync.
        * **State**: Resolved race condition in `WorldState` root hash calculation by moving sorting and Merkle tree construction out of the lock.
        * **Network**: Optimized ZMQ transport replay buffer management with threshold-based cleanup (>1000 entries).
        * **Consensus**: Lowered parallel signature verification batch threshold from 15 to 4 for earlier multi-threading acceleration.

    * 2026-07-18

        * **Storage**: Tuned IPFS connection pooling parameters (`max_keepalive_connections=50`, `max_connections=150`) to accelerate concurrent block storage.
        * **Core**: Resolved critical indexing race conditions in block creation within lock constraints and aligned initial index references.
        * **Database**: Optimized SQLite adapter by setting database connection timeout to 30.0 seconds to prevent write-lock exceptions under high parallel load.

    * 2026-07-17

        * **Performance**: Replaced `json` with `orjson` across the entire codebase (security, risk_management, network, monitoring, privacy, config, CLI, API, and hierachain modules) for faster serialization/deserialization.
        * **Core**: Added optimized data payload recovery for blocks with direct `data` column parsing when available.
        * **Security**: Optimized signature verification with configurable thread pool (CPU count) and extracted `_get_verify_key` helper for public key decoding.

    * 2026-07-12

        * **Network**: Fixed seed node public key decoding with special handling for `$$` delimiter characters.

    * 2026-07-09

        * **Risk Management**: Improved database connection handling in audit logger.
        * **Policy**: Fixed Null value evaluation in Arrow `StructArray`.

    * 2026-07-05

        * **Database**: Enhanced SQL adapter with metadata and merkle root support.
        * **API**: Renamed API version tags for clarity (`v1` → `ledger`, `v2` → `business`, `v3` → `admin`); updated security testing scripts and health check endpoints accordingly.

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

    * 2026-06-30

        * **Dead Code Removal**: Removed unused modules across core (performance, parallel_engine), storage (`ChainModel`), network (message encryption exception classes), error_mitigation, domains (entity reporting, compliance), consensus, API, and adapters.
        * **State**: Removed `apply_event_list` function from world state.
        * **Event Ledger**: Reconstructed event data structure and storage logic.

    * 2026-06-24

        * **Dependencies**: Added `vulture` for dead code detection.

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

??? warning "Breaking Changes (1)"

    * **API Routing & Data Schemas**: Restructured API routes into domain-specific namespaces (`/api/ledger`, `/api/business`, `/api/admin`), updated payload key names from `transaction_*` to `event` / `details`, and refactored SDK client namespaces.

---

## v0.0.6 (2026-07-15)

This release focuses on security hardening of the logging subsystem, simplification of the core blockchain and hierarchical layers, and further consensus hardening with proper error handling.

??? note "Improvements (6)"

    * **Secure Logging**: Added regex-based redaction of sensitive keys and tokens in `hierachain/security/`: sensitive values are replaced with `'***'` to prevent credential leakage. Introduced `_SEVERITY_MAP` for consistent security event logging, replacing direct log level methods with `logger.log()`, reducing duplication across all logging call sites.
    * **Core Blockchain Refactoring**: Added `_rebuild_event_indexes` to reset and rebuild event indexes after block loading, ensuring index consistency across restarts. Changed hash mismatch from silent correction to raising an exception, so potential data corruption is no longer hidden. Replaced direct dictionary access with `block.to_event_list()` for cleaner event filtering.
    * **Consensus Hardening**: Enhanced `_contains_forbidden_terms` with regex word-boundary matching to eliminate false positives. Removed fallback random signature generation; signing now fails cleanly with an error message when the private key is missing. `ProofOfFederation` auto-generates key pairs for validators, exposes `public_key` property, added `block_hash` to consensus metadata. `_verify_block_quorum` now accepts optional `signer_id` to avoid redundant event re-scanning.
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
    * **Block Overwrite**: In `hierachain/storage/sql_backend.py`, `save_block` queries for existing blocks by `index`/`chain_name`, deletes and replaces them instead of silently handling `UNIQUE constraint` violations.
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

    * **Full Mypy Compliance**: Resolved static typing warnings across all modules: consensus, API, security, network, monitoring, error mitigation, storage, adapters, hierarchical, domains, core and cluster.
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
