# HieraChain codebase reference

This reference maps the implementation under `hierachain/`. Paths below are relative to the repository root. For maintained behavior descriptions, use the paired [English code map](en/reference/code-map.md) and [Vietnamese code map](vi/reference/code-map.md).

HieraChain records business events in a two-tier ledger. Sub-Chains retain domain event data; the MainChain records proof anchors and hierarchy registration events. `HierarchyManager` coordinates lifecycle, durable recovery and proof submission.

## Event representation

The REST request schema uses `event_type`; stored ledger events use `event`. The Arrow event table has seven columns: `entity_id`, `event`, `timestamp`, `details`, `details_cid`, `details_nonce` and `data`. Canonical event payloads preserve nested JSON values for hashing and durable storage.

```mermaid
flowchart TD
    Manager["HierarchyManager"] --> Main["MainChain: proof anchors and registration"]
    Manager --> Sub["Sub-Chains: business events"]
    Sub -->|Explicit proof submission / cross-level sync| Main
```

## Core and state

| Source | Responsibility |
| --- | --- |
| `hierachain/core/block.py` | Arrow event tables, canonical payloads, block hashes and Merkle roots |
| `hierachain/core/blockchain.py` | Signed chain history, pending events, finalization and event indexes |
| `hierachain/core/event_query.py` | Entity/event query helpers |
| `hierachain/core/merkle_tree.py` | Merkle tree construction and proofs |
| `hierachain/core/cache.py` | Configurable LRU/LFU/FIFO/TTL cache strategies |
| `hierachain/core/parquet_log.py` | Parquet event-log utilities |
| `hierachain/core/utils.py` | Event construction and structure helpers |
| `hierachain/serialization.py` | Shared JSON and canonical JSON serialization |
| `hierachain/state/world_state.py` | State projection and snapshots from block events |

A block's structural check does not establish signature trust. Durable readers and writers use block verification with trusted public keys, including for genesis. See [Core](en/modules/core.md) · [Core tiếng Việt](vi/modules/core.md).

## Hierarchy and domains

| Source | Responsibility |
| --- | --- |
| `hierachain/hierarchical/main_chain/base.py` | MainChain lifecycle and consensus selection |
| `hierachain/hierarchical/main_chain/proofs.py` | Durable proof anchors and proof indexes |
| `hierachain/hierarchical/main_chain/registry.py` | Sub-Chain registration |
| `hierachain/hierarchical/sub_chain/base.py` | Sub-Chain lifecycle and ordering integration |
| `hierachain/hierarchical/sub_chain/ordering.py` | Ordering setup, consumption and finalization |
| `hierachain/hierarchical/sub_chain/proof.py` | Proof preparation and submission |
| `hierachain/hierarchical/hierarchy_manager/base.py` | Coordinator facade and storage selection |
| `hierachain/hierarchical/hierarchy_manager/recovery.py` | Restore and verify durable history |
| `hierachain/hierarchical/hierarchy_manager/registry.py` | Persist and restore hierarchy/access metadata |
| `hierachain/hierarchical/channel/` | Organization channel ledgers, policies and queries |
| `hierachain/hierarchical/multi_org.py` | Organization and network models |
| `hierachain/hierarchical/private_data.py` | Private-collection and endorsement models |
| `hierachain/hierarchical/transaction_manager.py` | Cross-chain two-phase commit coordinator |
| `hierachain/domains/chains/base_chain.py` | Entity registry, operation projection and domain rules |
| `hierachain/domains/chains/domain_chain.py` | Domain operations and participant behavior |
| `hierachain/domains/chains/tx_manager.py` | Participant prepare/commit/rollback handling |
| `hierachain/domains/chains/metrics.py` | Operation counts and success/quality/approval rates |
| `hierachain/domains/events/` | Base/domain event models and event factories |
| `hierachain/domains/utils/entity_tracer.py` | Cross-chain entity traces and lifecycle summaries |
| `hierachain/domains/utils/cross_chain_validator.py` | Proof, entity and ledger terminology checks |

`HierarchyManager.create_sub_chain()` creates a `DomainChain`; the REST chain-creation route creates a base `SubChain`. These entry points do not expose the same domain participant behavior. `EntityTracer.trace_entity()` returns per-chain summaries under `chain_details`. Operation metrics do not include latency percentiles.

Two-phase commit records the commit decision before participant commit calls. A missing acknowledgement after that decision leads to forward recovery or `IN_DOUBT`; rollback applies to prepare failures before the durable commit decision.

See [Hierarchy](en/modules/hierarchical.md) · [Phân cấp](vi/modules/hierarchical.md), and [Domains](en/modules/domains.md) · [Domain](vi/modules/domains.md).

## Consensus and ordering

MainChain selects PoA or PoF through `HRC_MAINCHAIN_CONSENSUS`; `HRC_CONSENSUS_TYPE` is a fallback alias. SubChain defaults to PoA and accepts `consensus_type` in its constructor config. Setting a BFT name does not activate the separate BFT engine.

| Source | Responsibility |
| --- | --- |
| `hierachain/consensus/proof_of_authority.py` | Authority-based block creation and validation; default spacing is 0 seconds |
| `hierachain/consensus/proof_of_federation.py` | Validator registration and rotating leader schedule; separate 5-second interval |
| `hierachain/consensus/bft/` | BFT engine, dispatcher, message types and view changes |
| `hierachain/consensus/ordering/service.py` | Ordering facade, event acceptance and lifecycle |
| `hierachain/consensus/ordering/certifier.py` | Event certification |
| `hierachain/consensus/ordering/block_builder.py` | Event batches |
| `hierachain/consensus/ordering/processor.py` | Asynchronous certification and processing |
| `hierachain/consensus/ordering/block_manager.py` | Block finalization, signing and commit |
| `hierachain/consensus/ordering/storage.py` | Trusted block verification and persistence |
| `hierachain/consensus/ordering/recovery.py` | Journal replay and recovery |
| `hierachain/consensus/ordering/maintenance.py` | Ordering pause, lockdown and resume |
| `hierachain/consensus/ordering/metrics.py` | Ordering statistics |

PoF uses `Validators[block_index % validator_count]` for the expected leader. Its ordinary block verification checks that leader's trusted signature; the separate quorum helper does not automatically collect multiple signatures or provide leader failover. BFT requires explicit application integration and is not the MainChain/SubChain ordering backend.

```mermaid
flowchart LR
    Caller["REST / SDK / CLI / Python caller"] --> Access["Entry-point access checks, where applicable"]
    Access --> Journal["Journal event acceptance"]
    Journal --> Order["Queue, certify and batch"]
    Order --> Block["Finalize and sign block"]
    Block --> Store["Verify trusted block and persist"]
    Store --> Consume["Consume committed block and update projection"]
    Consume --> Anchor["Explicit proof submission / cross-level sync"]
```

This diagram describes the Sub-Chain ordering path. API acknowledgement is distinct from finalized block/proof visibility. WebSocket helpers deliver notifications and do not submit ledger events. Policy evaluation is specific to each entry point; it is not an automatic step for every direct Python operation.

See [Consensus](en/architecture/consensus.md) · [Đồng thuận](vi/architecture/consensus.md).

## Storage and recovery

| Source | Responsibility |
| --- | --- |
| `hierachain/adapters/database/sqlite_adapter.py` | Durable SQLite blocks and hierarchy/channel data |
| `hierachain/adapters/database/postgres_adapter.py` | Durable PostgreSQL blocks and hierarchy/channel data |
| `hierachain/adapters/database/redis_adapter.py` | Auxiliary Redis state operations |
| `hierachain/adapters/database/redis_rate_limiter.py` | Redis rate-limiter backend |
| `hierachain/adapters/database/auth_state.py` | Persistent API authentication state |
| `hierachain/adapters/database/audit_manifest.py` | Trusted audit digest manifest storage |
| `hierachain/error_mitigation/journal.py` | Length-framed Arrow journal batches and event replay |
| `hierachain/error_mitigation/error_classifier.py` | Error classification and configured recovery callbacks |
| `hierachain/error_mitigation/validator.py` | Business validation coordinator |
| `hierachain/error_mitigation/data_validator.py` | Input validation helpers |
| `hierachain/cluster/cross_level_sync.py` | Proof synchronization and cross-level state tracking |

The hierarchy accepts SQLite, PostgreSQL or process-local memory storage. It rejects Redis as a durable signed-block backend. CLI chain/event commands require SQLite or PostgreSQL. Preserve both the database and the per-chain ordering journals for recovery.

`ErrorClassifier` does not automatically dispatch every error to journal or BFT recovery. Recovery depends on configured callbacks and the owning component's actual error-handling path.

## API, clients and CLI

| Source | Responsibility |
| --- | --- |
| `hierachain/api/server.py` | FastAPI app, middleware, router registration and startup/shutdown |
| `hierachain/api/ledger/router.py`, `hierachain/api/ledger/schemas.py` | Ledger routes and request/response schemas |
| `hierachain/api/ledger/` | Ledger endpoint implementations |
| `hierachain/api/business/router.py`, `hierachain/api/business/schemas.py` | Business routes and schemas |
| `hierachain/api/business/` | Business endpoint implementations |
| `hierachain/api/admin/endpoints.py` | Admin identity/status endpoints |
| `hierachain/api/graphql/` | GraphQL schema, resolvers, types and query checks |
| `hierachain/api/websocket/` | Connections, subscriptions, message builders and broadcast helpers |
| `hierachain/api/blockchain_explorer.py`, `hierachain/api/explorer_components.py` | Explorer dashboard and component handlers |
| `hierachain/api/storage/ipfs_client.py`, `hierachain/api/storage/encryption.py` | Explicit IPFS upload/download with AES-256-GCM |
| `hierachain/api/storage/endpoint_helpers.py` | Inline/CID selection and optional CID resolution |
| `hierachain/sdk/client.py`, `hierachain/sdk/async_client.py` | Sync/async HTTP clients with retry and circuit-breaker handling |
| `hierachain/cli/` | Click command groups: `chain`, `event`, `key`, `node`, `verify` |
| `hierachain/cli/store.py` | Config loading and invocation-owned durable hierarchy manager |

The REST groups are named `/api/ledger`, `/api/business` and `/api/admin`; they are not numbered API versions. WebSocket broadcasts need application integration with commit/event paths. The default `all` subscription receives explicit `broadcast_to_all()` messages; per-chain broadcasts require a named chain subscription.

Contract registration stores implementation/CID and metadata in API-process memory. Contract execution and private-data writes return HTTP 501 for known resources and HTTP 404 for unknown contracts/collections after request validation and authorization. Collection models do not provide a working REST private-data store.

Event and contract routes accept inline payloads or existing CID references; they do not automatically upload large payloads. The environment-configured IPFS client requires a stable `HRC_IPFS_ENCRYPTION_KEY` containing 64 hexadecimal characters. SDK CID resolution is opt-in.

CLI chains attach to `--parent main`; nested parent chains are unsupported. `store.py` reuses configured durable storage across invocations rather than persisting chain history in a CLI JSON cache. Use `hrc --help` and each group's `--help` for exact arguments.

See [Ledger API](en/reference/api-ledger.md) · [API ledger tiếng Việt](vi/reference/api-ledger.md), [Business API](en/reference/api-business.md) · [API business tiếng Việt](vi/reference/api-business.md), and [CLI](en/modules/cli.md) · [CLI tiếng Việt](vi/modules/cli.md).

## Security

| Source | Responsibility |
| --- | --- |
| `hierachain/security/identity_loader.py` | Load the persistent signing/transport identity and trusted block keys |
| `hierachain/security/identity.py` | User identity records and explicit signature helpers |
| `hierachain/security/msp.py` | Custom certificates, organization roles and authorization helpers |
| `hierachain/security/policy_engine.py`, `hierachain/security/policy_types.py` | Conditional policies, policy sets, cache and evaluation audit |
| `hierachain/security/key_manager.py` | API key lifecycle and cached lookups |
| `hierachain/security/key_provider.py` | Signing-provider interface, local key provider and password-encrypted file vault |
| `hierachain/security/brute_force_protector.py` | Failed authentication tracking |
| `hierachain/security/verify/api_key_verifier.py` | Request API key, permissions and brute-force checks |
| `hierachain/security/verify/block_verifier.py` | Canonical hash, Merkle, chain-link and trusted signature checks |
| `hierachain/security/verify/signature_verifier.py` | Signature verification helpers |
| `hierachain/security/security_utils.py` | Ed25519 key-pair and signing utilities |
| `hierachain/security/sanitization.py` | Context-specific string/data transformations |
| `hierachain/security/secure_logging.py` | Security/audit logging helpers |
| `hierachain/security/zk_prover.py`, `hierachain/security/verify/zk_verifier.py` | Mock ZK proving/verification; production backend hooks raise `NotImplementedError` |

API-key authentication is conditional in base/dev/test settings and mandatory in production. MSP and policy helpers need explicit use; their presence does not authenticate every Python operation. Sanitization is not a complete SQL/NoSQL/shell injection or schema-validation boundary.

Hierarchical block signing uses Ed25519. The standalone `BlockVerifier` also supports trusted PEM EC/RSA/Ed25519/Ed448 public keys. `verify_chain()` checks the supplied sequence, including genesis, but does not prove it reaches an independently expected latest tip; an empty sequence is accepted.

See [Authorization](en/security/authorization-access-control.md) · [Phân quyền](vi/security/authorization-access-control.md), and [ZK scope](en/architecture/zk-proofs.md) · [Phạm vi ZK](vi/architecture/zk-proofs.md).

## Network, integration and operations

| Source | Responsibility |
| --- | --- |
| `hierachain/network/zmq_transport.py` | ZeroMQ ROUTER/DEALER transport, optional CurveZMQ and replay checks |
| `hierachain/network/network_client.py` | P2P peer registry and message dispatch |
| `hierachain/network/secure_connection.py` | Optional CurveZMQ/MSP handshake and signature checks |
| `hierachain/network/peer_trust_manager.py` | Explicit allowlist/blocklist with open/strict policy |
| `hierachain/network/message_cryptographic.py` | Message signing/verification |
| `hierachain/integration/enterprise.py` | SAP/Oracle/Dynamics simulation fixtures |
| `hierachain/integration/erp_ledger.py`, `hierachain/integration/erp/` | ERP mapping, change detection, scheduling and ledger coordination |
| `hierachain/monitoring/alert_system.py` | Rule evaluation, alert lifecycle and configured email/webhook delivery |
| `hierachain/monitoring/performance_monitor.py` | Background metrics collection and threshold checks |
| `hierachain/risk_management/audit_logger.py` | Audit storage/query/reporting with optional trusted digest verification |

`NetworkClient` is a ZeroMQ P2P client, not an HTTP client. The API runtime constructs `ZmqNode` directly and does not automatically apply `SecureConnectionManager`'s MSP handshake, peer trust policy or message-signature settings. TLS termination for HTTP belongs to the deployment gateway.

Vendor ERP fixtures require `simulation_mode=True`. Applications must supply real ERP connectors. There is no Arrow Flight client, ERP adapter directory or Kubernetes namespace manager under `hierachain/`.

`AlertManager.check_metric()` first adds the sample, then evaluates matching enabled rules and cooldowns. Z-score detection runs for an explicit `anomaly` rule; it is not a prerequisite for threshold rules. Email/webhook delivery requires notifier configuration.

Audit archives are not inherently immutable. Integrity reads require a separately trusted digest manifest; `query_events_with_integrity()` returns `UNVERIFIED` without a digest reader and fails closed on manifest errors or mismatches.

See [Network](en/modules/network.md) · [Mạng](vi/modules/network.md), [Risk alerts](en/workflows/risk-alerts.md) · [Cảnh báo rủi ro](vi/workflows/risk-alerts.md), and [Deployment](en/architecture/deployment.md) · [Triển khai](vi/architecture/deployment.md).

## Configuration

Load environment variables before importing HieraChain. `settings.py` reads the dotenv path selected by `HRC_ENV_FILE`. Environment subclasses override some base defaults, and validation helpers return messages for callers to handle; they do not automatically validate every startup setting.

| Variable | Current behavior |
| --- | --- |
| `HRC_ENV` | Selects development/test/production settings; development is the fallback |
| `HRC_MAINCHAIN_CONSENSUS` | MainChain PoA/PoF selection; fallback alias `HRC_CONSENSUS_TYPE`, default `proof_of_authority` |
| `HRC_BLOCK_INTERVAL` | PoA spacing, default 0; PoF keeps its separate 5-second interval |
| `HRC_STORAGE_BACKEND` | Explicit storage choice; otherwise infer SQLite/PostgreSQL from the configured database URL or use the environment default |
| `DATABASE_URL` / `HRC_DATABASE_URL` | First nonblank value wins, in that order |
| `HRC_VALIDATOR_IDENTITY` | Persistent node identity path, default `validator_key.json` |
| `HRC_BLOCK_TRUSTED_KEYS_FILE` | Operator-provisioned trusted public-key map for block history |
| `HRC_AUTH_ENABLED` | Base/dev/test default false; production requires true |
| `HRC_ENABLE_ZK_PROOFS` / `HRC_ZK_MODE` | ZK enable flag defaults false; mode defaults mock; production hooks remain unimplemented |
| `HRC_IPFS_ENABLED` | API CID resolution integration, default false |
| `HRC_IPFS_HOST` | IPFS API multiaddr, default `/ip4/127.0.0.1/tcp/5001` |
| `HRC_IPFS_ENCRYPTION_KEY` | Stable 32-byte key encoded as 64 hex characters; required by the environment factory |
| `HRC_IPFS_AUTO_PIN` | Pin uploads, default true |

Base/development/production storage defaults to PostgreSQL; test settings default to memory unless a backend or database URL is supplied. The default database string is `postgresql://hiera:hiera@localhost:5432/hierachain`; production PostgreSQL startup requires an explicitly configured URL.

For complete defaults, startup requirements and integration limits, use [Configuration](en/reference/config.md) · [Cấu hình](vi/reference/config.md). For development commands, use [Developer guide](DEV_GUIDE.md).
