---
title: "Configuration"
description: "Environment variables and settings in hierachain/config/settings.py; override methods and default values."
icon: material/tune
---

# System configuration

## Purpose

This page lists the main HieraChain settings, their defaults, and how to override them. All values are defined in `hierachain/config/settings.py` and read from environment variables or constants.

## Scope

* Applies to API, CLI, and Sub-Chain/Main Chain components that run in the same Python process.
* Does not cover deployment plumbing such as Kubernetes manifests or reverse proxies. It only covers vars that HieraChain reads directly.

## Accessing configuration in code

```python
from hierachain.config.settings import settings

print(settings.API_HOST, settings.API_PORT)
print(settings.CONSENSUS_TYPE)
print(settings.AUTH_ENABLED)
```

## Environment variables and defaults

### Runtime environment

* `HRC_ENV` selects the config class; `ENV` is used when `HRC_ENV` is unset or blank. `HRC_ENV` takes precedence when both are set. Values are case-insensitive and ignore surrounding whitespace: `dev` / `development`, `test` / `testing`, or `production` / `prod` / `product` (default when both are blank: development). An unknown nonblank value raises an error instead of selecting development.
* `.env` is loaded before environment-backed settings are defined. Set `HRC_ENV_FILE` to use another dotenv file. Existing process environment values take precedence over values in that file.

### API

* `HRC_API_HOST` (default: `localhost` in dev, `127.0.0.1` in production)
* `HRC_API_PORT` (default: `2661`)
* `API_VERSION` (constant: `ledger`; business/admin routes have their own prefixes)

### Consensus and blockchain

* `HRC_CONSENSUS_TYPE` / `HRC_MAINCHAIN_CONSENSUS` (alias, default: `proof_of_authority`; supported: `proof_of_authority`, `proof_of_federation`)

* `HRC_BLOCK_INTERVAL` (default `0.0` seconds): additional PoA spacing; a positive interval requires at least half that spacing during validation. It does not control PoF. Default Sub-Chain batching still uses 50 events and a 1-second timeout.
* `CONSENSUS_FEDERATION_CONFIG`: federation config (min_validators: 3, block_interval: 5.0). This is a Settings attribute, not an env var.
* `VALIDATOR_TIMEOUT` (default: `30` seconds). Settings attribute.
* `BFT_ENABLED` (default: `True`), `BFT_FAULT_TOLERANCE` (default: `1`), `BFT_NODE_COUNT` (default: `4`). Settings attributes (no `HRC_BFT_ENABLED` env var).
* Block limits: `BLOCK_SIZE_LIMIT` (default: `1000` events/block in dev, `10` in test)
* `PROOF_SUBMISSION_INTERVAL` (default: `300` seconds in dev, `10` in test)
* `HRC_VALIDATOR_IDENTITY`: complete node identity file path (default: `validator_key.json`). It requires node/MSP IDs, signing private/public keys and transport private/public keys; the two-field `hrc key generate` output alone is insufficient. See [Quickstart](../getting-started/quickstart.md).
* `HRC_BLOCK_TRUSTED_KEYS_FILE`: required JSON file mapping `creator_id` to Ed25519 public-key hex. The local key in `HRC_VALIDATOR_IDENTITY` must match its entry. Missing or mismatched files stop chain/API startup. Every block, including genesis, requires a trusted signature. Existing unsigned chains need migration before startup.

### Storage and cache

* `HRC_STORAGE_BACKEND` / `DATABASE_URL` / `HRC_DATABASE_URL` (defaults: `postgres` in development and production, `memory` in tests; recognized values: `sqlite`, `postgres` / `postgresql`, `redis`, `memory`). An unknown backend stops API startup and chain storage initialization. `HierarchyManager` also rejects `redis` at startup because durable signed-block persistence is unavailable; use `sqlite` or `postgres` for durable ledger storage. Redis remains available for the separate indexing, authentication-state, and rate-limit adapters.
* In production, when the selected backend is PostgreSQL, set `DATABASE_URL` or `HRC_DATABASE_URL` explicitly. API startup rejects the built-in local fallback URL; it does not test database connectivity.
* `DATABASE_URL` takes precedence when nonblank. An empty or whitespace-only value falls back to `HRC_DATABASE_URL`.
* If PostgreSQL is unavailable, chain storage initialization fails. Set `HRC_STORAGE_BACKEND=sqlite` to select SQLite explicitly.
* Cache instances: `AdvancedCache(max_size=10000, eviction_policy="lru")` accepts per-instance settings; `set(key, value, ttl=...)` sets entry TTL. `KeyManager` uses its own key/permission caches and `cache_ttl` (default: `300` seconds). Ordering's `block_cache_size` remains a service configuration key (default: `100`), not a `Settings` attribute.
* Removed unused configuration: `ADVANCED_CACHING_ENABLED`, `BLOCK_CACHE_SIZE`, `EVENT_CACHE_SIZE`, `ENTITY_CACHE_SIZE`, `BLOCK_CACHE_POLICY`, `EVENT_CACHE_POLICY`, `ENTITY_CACHE_POLICY`, `ENTITY_TTL`, and `hierachain.core.cache.DEFAULT_CACHE_CONFIG`. These names never controlled runtime caches; remove direct imports/accesses and configure the cache instance or service that actually uses them.
* DB: `DATABASE_URL` (development fallback: `postgresql://hiera:hiera@localhost:5432/hierachain`; do not rely on this fallback in production)
* Redis: `HRC_REDIS_HOST` or `REDIS_HOST` (`localhost`), `HRC_REDIS_PORT` or `REDIS_PORT` (`6379`), `REDIS_DB` (`0`). HRC-prefixed names take precedence.

### IPFS (off-chain storage)

* `HRC_IPFS_ENABLED` (default: `false`). Turns IPFS on or off for large data.
* `HRC_IPFS_HOST` (default: `/ip4/127.0.0.1/tcp/5001`). IPFS daemon address.
* `HRC_IPFS_AUTO_PIN` (default: `true`). Pins data after upload so it is not garbage collected.
* `HRC_IPFS_TIMEOUT` (default: `120` seconds). Max wait for IPFS calls.
* `HRC_IPFS_ENCRYPTION_KEY`: required by the IPFS environment factory, exactly 64 hex characters (32 bytes). Missing or invalid values raise `IPFSError`. Nodes reading the same encrypted object need the same key, nonce and metadata AAD; preserve the key across restarts.

### Parallel processing and resources

* `HRC_EVENT_POOL_MAX_SIZE` (default: `10000`) bounds the ordering event queue.
* `HRC_RAM_CRITICAL_THRESHOLD` (default: `95.0` %) is declared in settings but has no runtime consumer in ordering or storage.

### Security and authentication

* Authentication: `HRC_AUTH_ENABLED` (default `false` in dev/test and required `true` in production; an explicit `false` prevents production startup)
* `HRC_API_KEYS_FILE`: required in production. Path to a readable, nonempty JSON key map; keys must be at least 32 characters and each entry needs a `user_id` and nonempty `permissions` list. The file is loaded when the API app starts; changing the key map still requires recreating each node or restarting each direct process.
* `HRC_API_KEY_REVOCATIONS_DB` (default: `data/api_key_revocations.sqlite3`): durable local API key revocations and brute-force lockouts for the production API. All workers on one host must use the same persistent, writable file.
* `HRC_AUTH_STATE_REDIS_URL` (optional): when set, API key revocations and brute-force lockouts use the same Redis instance across hosts. Configure Redis persistence if revocations must survive a Redis restart. Backend errors reject authentication rather than using local state.
* `HRC_API_KEY_LOCATION` (`header`), `HRC_API_KEY_NAME` (`X-API-Key`)
* Secret backend: `HRC_SECRET_BACKEND` (values: `env`, `vault`, `aws`). Default is `env`; another value raises `ValueError`.
* AWS Secret Manager: `HRC_AWS_SECRET_NAME` (required secret name or ARN containing a JSON object), `HRC_AWS_REGION` (default: `us-east-1`). `SecretManager.get_secret(key)` selects a string field, never the whole `SecretString`; see [Secret Manager](../modules/config.md) for defaults and migration.
* `HRC_MASTER_KEY_SOURCE=env` remains accepted as a compatibility alias for the existing environment-secret behavior. Other `HRC_MASTER_KEY_SOURCE` values and any nonempty `HRC_MASTER_KEY_FILE` now stop configuration loading with an error because no alternate master-key provider is implemented. This does not change the separate `FileVaultProvider` API.
* Brute-force protection:
    * `HRC_BF_MAX_FAILURES` (default: `5`)
    * `HRC_BF_LOCKOUT_SECONDS` (default: `900` = 15 minutes)
    * `HRC_BF_WINDOW_SECONDS` (default: `300` = 5 minutes)
    * Redis lockout TTL follows `HRC_BF_LOCKOUT_SECONDS`; lockout checks read the shared key on each request. SQLite and Redis count failures atomically across workers. Redis uses its server time and an atomic Lua update for the failure window and lockout threshold. Memory/file attempt counts remain local to one process.
* Identity and organization: `IDENTITY_MANAGER_ENABLED` (`True`), `REQUIRE_ORGANIZATION_VALIDATION` (`True`), `MSP_ENABLED` (`True`)

### P2P network security

* Node identity and P2P transport: `HRC_NODE_ID` (default: `default-node`; `NODE_ID` is a fallback alias), `HRC_P2P_PORT` (default: `5555`; `NODE_PORT` is a fallback alias), and `HRC_PEERS` (default: empty list; comma-separated seed nodes; `PEERS` is a fallback alias). Use `peer-id@host:port` when the remote transport identity differs from its hostname; plain `host:port` treats the hostname as the peer ID. HRC-prefixed names take precedence.
* `HRC_P2P_TRUST_POLICY` (default: `open` in dev, `strict` in production; values: `open|strict`)
* `HRC_P2P_PEER_ALLOWLIST` (comma-separated peer IDs for strict mode)
* `HRC_P2P_REQUIRE_SIGNATURES` (`false` in dev, `true` in production)

Production fixes the trust policy to `strict` and the signature requirement to `True`; environment values do not override those production attributes. `SecureConnectionManager` uses these settings. The API startup path constructs `NetworkClient` with seed peers and transport keys, without wiring this manager, the trust policy or signature verification into that client. See [Network](../modules/network.md).

### CORS

* `HRC_CORS_ALLOW_ALL` (`true` in dev, `false` in production)
* `HRC_CORS_ORIGINS` (CSV list of domains; production requires explicit values)
* `CORS_ALLOW_METHODS` (list of allowed methods)
* `CORS_ALLOW_HEADERS` (list of allowed headers)

### HTTPS and HSTS

* `HRC_HSTS_ENABLED` (`false` in dev/test; `true` in production)
* `HRC_HSTS_MAX_AGE` (default: `31536000` = 1 year)

These settings are declared and checked for configuration warnings, but the API middleware does not add `Strict-Transport-Security`. Configure the header at the HTTPS reverse proxy.

### Rate limiting

* `HRC_RATE_LIMIT` (`false` in dev/test; `true` in production)
* `HRC_RATE_LIMIT_RPM` (default: `100` requests/minute)
* `HRC_RATE_LIMIT_BACKEND`: `memory` (single node) or `redis` (multi-node or cluster).
* With the `redis` backend, Redis errors and timeouts reject non-exempt requests with HTTP 503 (fail-closed). Redis checks run off the API event loop.

### Monitoring and metrics

* `HRC_METRICS_ENABLED` (default: `false`). Enables `/metrics` to export the default Prometheus registry. No HTTP latency/request counters or ledger collectors are registered by the API.
* `HRC_TRUSTED_PROXIES` (default: `127.0.0.1`). Trusted reverse proxy IPs (for HTTP/2, HTTP/3).

### Multi-organization

* `MULTI_ORG_ENABLED` (`True`), `MSP_ENABLED` (`True`)
* `ORGANIZATION_ADMIN_THRESHOLD` (default: `1`)
* `CHANNEL_CREATION_POLICY` (default: `majority`; values: `majority|unanimous|admin_only`)
* `AFFILIATION_HIERARCHY_ENABLED` (`True`)

### Zero-knowledge (ZK)

* `HRC_ENABLE_ZK_PROOFS` (default: `false`)
* `HRC_ZK_MODE` (`mock` or `production`, default `mock`)
* `HRC_ZK_VERIFICATION_KEY`, `HRC_ZK_PROVING_KEY`, `HRC_ZK_CIRCUIT` (file paths)
* `HRC_ZK_REQUIRED_MAINCHAIN` (default: `false`)

Mock is for development only; `production` proving/verifying is unimplemented. Enabling flags or configuring keys/circuits does not supply a production backend.

### Cross-level state sync

* `HRC_CROSS_LEVEL_SYNC` (default: `true`)
* `HRC_CROSS_LEVEL_BATCH` (default: `100`)
* `HRC_CROSS_LEVEL_TIMEOUT` (default: `30.0` seconds)

### Integration

* `ERP_INTEGRATION_ENABLED` (`True`)
* `SUPPORTED_ERP_SYSTEMS` (list: `sap`, `oracle`, `microsoft_dynamics`)

These attributes do not start ERP sync in the API. Built-in vendor connectors are `simulation_mode=True` fixtures; applications must provide real adapters.

### Declared settings without runtime consumers

`HRC_BLOCK_CREATION_MODE`, `HRC_BLOCK_MAX_WAIT_SEC`, `HRC_PARQUET_ROLL_INTERVAL`, `HRC_POSTGRES_SYNC_MODE` and `HRC_SQL_RETENTION_DAYS` are read into settings but have no runtime consumers under `hierachain/`. Setting them does not change batching, rotate Parquet, start a SQL batch worker or purge old events automatically. Configure batching on the ordering service/Sub-Chain itself.

### Logging

* `LOG_LEVEL`: the selected environment class fixes this attribute to `DEBUG` in dev/test and `WARNING` in production. Setting the `LOG_LEVEL` environment variable does not override those class values.
* `LOG_FORMAT` (standard Python logging format string).
* `HRC_LOG_FORMAT`: `text` (default) or `json` (for centralized logging like ELK/Loki).
* `HRC_LOG_SQL_DETAIL` (default: `false`)

The launchers configure Uvicorn separately: `python -m hierachain` selects `debug` for a DEBUG settings level and `info` otherwise; `hrc node start` uses `info`. `HRC_LOG_FORMAT` controls the application formatter.

### CLI

* `CLI_CONFIG_FILE` (default: `data/config.yaml`; default node config used by `hrc --config`)
* `CLI_LOG_LEVEL` (default: `INFO`)

## Example .env (development)

Add a signing identity and trusted-key map from the [Quickstart](../getting-started/quickstart.md) before initializing chains.

```dotenv
HRC_ENV=dev
HRC_API_HOST=0.0.0.0
HRC_API_PORT=2661
HRC_CONSENSUS_TYPE=proof_of_authority
HRC_AUTH_ENABLED=false
HRC_CORS_ALLOW_ALL=true
DATABASE_URL=postgresql://hiera:hiera@localhost:5432/hierachain
```

## Recommended production configuration (minimum)

```dotenv
HRC_ENV=production
HRC_API_KEYS_FILE=/run/secrets/api_keys.json
HRC_VALIDATOR_IDENTITY=/run/secrets/identity.json
HRC_BLOCK_TRUSTED_KEYS_FILE=/run/secrets/trusted_block_keys.json
HRC_API_KEY_REVOCATIONS_DB=/var/lib/hierachain/api_key_revocations.sqlite3
HRC_NODE_ID=node1
HRC_API_HOST=0.0.0.0
HRC_AUTH_ENABLED=true
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=https://portal.example.com
HRC_RATE_LIMIT=true
DATABASE_URL=postgresql://user:pass@db:5432/hierachain
HRC_STORAGE_BACKEND=postgres
HRC_IPFS_ENABLED=true
HRC_IPFS_HOST=/ip4/ipfs/tcp/5001
HRC_IPFS_ENCRYPTION_KEY=your_32_byte_hex_key_here
```
