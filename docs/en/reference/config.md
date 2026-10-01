---
title: "Configuration"
description: "Environment variables and settings in hierachain/config/settings.py; override methods and default values."
icon: material/tune
---

# System Configuration

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

### API

* `HRC_API_HOST` (default: `localhost` in dev, `127.0.0.1` in production)
* `HRC_API_PORT` (default: `2661`)
* `API_VERSION` (constant: `ledger` as defined in `hierachain/config/settings.py:189`, not `admin`)

### Consensus and blockchain

* `HRC_CONSENSUS_TYPE` / `HRC_MAINCHAIN_CONSENSUS` (alias, default: `proof_of_authority`; supported: `proof_of_authority`, `proof_of_federation`)
* `CONSENSUS_FEDERATION_CONFIG`: federation config (min_validators: 3, block_interval: 5.0). This is a Settings attribute, not an env var.
* `VALIDATOR_TIMEOUT` (default: `30` seconds). Settings attribute.
* `BFT_ENABLED` (default: `True`), `BFT_FAULT_TOLERANCE` (default: `1`), `BFT_NODE_COUNT` (default: `4`). Settings attributes (no `HRC_BFT_ENABLED` env var).
* Block limits: `BLOCK_SIZE_LIMIT` (default: `1000` events/block in dev, `10` in test)
* `PROOF_SUBMISSION_INTERVAL` (default: `300` seconds in dev, `10` in test)
* `HRC_VALIDATOR_IDENTITY`: validator identity file path (default: `validator_key.json`)
* `HRC_BLOCK_TRUSTED_KEYS_FILE`: required JSON file mapping `creator_id` to Ed25519 public-key hex. The local key in `HRC_VALIDATOR_IDENTITY` must match its entry. Missing or mismatched files stop chain/API startup. Every block, including genesis, requires a trusted signature. Existing unsigned chains need migration before startup.

### Storage and cache

* `HRC_STORAGE_BACKEND` / `DATABASE_URL` / `HRC_DATABASE_URL` (defaults: `postgres` in development and production, `memory` in tests; supported values: `sqlite`, `postgres` / `postgresql`, `redis`, `memory`). An unknown backend stops API startup and chain storage initialization.
* In production, when the selected backend is PostgreSQL, set `DATABASE_URL` or `HRC_DATABASE_URL` explicitly. API startup rejects the built-in local fallback URL; it does not test database connectivity.
* `DATABASE_URL` takes precedence when nonblank. An empty or whitespace-only value falls back to `HRC_DATABASE_URL`.
* If PostgreSQL is unavailable, chain storage initialization fails. Set `HRC_STORAGE_BACKEND=sqlite` to select SQLite explicitly.
* Advanced caching: `ADVANCED_CACHING_ENABLED` (default: `True`)
* `BLOCK_CACHE_SIZE` (default: `5000`), `EVENT_CACHE_SIZE` (`20000`), `ENTITY_CACHE_SIZE` (`10000`)
* Cache policies: `BLOCK_CACHE_POLICY` (`lru`), `EVENT_CACHE_POLICY` (`ttl`), `ENTITY_CACHE_POLICY` (`lfu`)
* `ENTITY_TTL` (default: `3600` seconds)
* DB: `DATABASE_URL` (development fallback: `postgresql://hiera:hiera@localhost:5432/hierachain`; do not rely on this fallback in production)
* Redis: `REDIS_HOST` (`localhost`), `REDIS_PORT` (`6379`), `REDIS_DB` (`0`)

### IPFS (off-chain storage)

* `HRC_IPFS_ENABLED` (default: `false`). Turns IPFS on or off for large data.
* `HRC_IPFS_HOST` (default: `/ip4/127.0.0.1/tcp/5001`). IPFS daemon address.
* `HRC_IPFS_AUTO_PIN` (default: `true`). Pins data after upload so it is not garbage collected.
* `HRC_IPFS_TIMEOUT` (default: `120` seconds). Max wait for IPFS calls.
* `HRC_IPFS_ENCRYPTION_KEY`: AES-256 key (32-byte hex). All nodes in the same channel or organization must use the same value.

### Parallel processing and resources

* DoS protection: `HRC_EVENT_POOL_MAX_SIZE` (default: `10000`), `HRC_RAM_CRITICAL_THRESHOLD` (`95.0` %)

### Security and authentication

* Authentication: `HRC_AUTH_ENABLED` (default `false` in dev/test and required `true` in production; an explicit `false` prevents production startup)
* `HRC_API_KEYS_FILE`: required in production. Path to a readable, nonempty JSON key map; keys must be at least 32 characters and each entry needs a `user_id` and nonempty `permissions` list. The file is loaded when the API app starts; changing the key map still requires recreating each node or restarting each direct process.
* `HRC_API_KEY_REVOCATIONS_DB` (default: `data/api_key_revocations.sqlite3`): durable local API key revocations and brute-force lockouts for the production API. All workers on one host must use the same persistent, writable file.
* `HRC_AUTH_STATE_REDIS_URL` (optional): when set, API key revocations and brute-force lockouts use the same Redis instance across hosts. Configure Redis persistence if revocations must survive a Redis restart. Backend errors reject authentication rather than using local state.
* `HRC_API_KEY_LOCATION` (`header`), `HRC_API_KEY_NAME` (`X-API-Key`)
* Secret backend: `HRC_SECRET_BACKEND` (values: `env`, `vault`, `aws`). Default is `env`.
* AWS Secret Manager: `HRC_AWS_SECRET_NAME` (required secret name or ARN containing a JSON object), `HRC_AWS_REGION` (default: `us-east-1`). `SecretManager.get_secret(key)` selects a string field, never the whole `SecretString`; see [Secret Manager](../modules/config.md) for defaults and migration.
* Master key: `HRC_MASTER_KEY_SOURCE` (`auto` in dev/test, `env` in production), `HRC_MASTER_KEY_FILE` (default: `config/master_backup_key.key`)
* Brute-force protection:
    * `HRC_BF_MAX_FAILURES` (default: `5`)
    * `HRC_BF_LOCKOUT_SECONDS` (default: `900` = 15 minutes)
    * `HRC_BF_WINDOW_SECONDS` (default: `300` = 5 minutes)
    * Redis lockout TTL follows `HRC_BF_LOCKOUT_SECONDS`; lockout checks read the shared key on each request. Failure counts remain process-local.
* Identity and organization: `IDENTITY_MANAGER_ENABLED` (`True`), `REQUIRE_ORGANIZATION_VALIDATION` (`True`), `MSP_ENABLED` (`True`)

### P2P network security

* `HRC_P2P_TRUST_POLICY` (default: `open` in dev, `strict` in production; values: `open|strict`)
* `HRC_P2P_PEER_ALLOWLIST` (comma-separated peer IDs for strict mode)
* `HRC_P2P_REQUIRE_SIGNATURES` (`false` in dev, `true` in production)

### CORS

* `HRC_CORS_ALLOW_ALL` (`true` in dev, `false` in production)
* `HRC_CORS_ORIGINS` (CSV list of domains; production requires explicit values)
* `CORS_ALLOW_METHODS` (list of allowed methods)
* `CORS_ALLOW_HEADERS` (list of allowed headers)

### HTTPS and HSTS

* `HRC_HSTS_ENABLED` (`false` in dev/test; `true` in production)
* `HRC_HSTS_MAX_AGE` (default: `31536000` = 1 year)

### Rate limiting

* `HRC_RATE_LIMIT` (`false` in dev/test; `true` in production)
* `HRC_RATE_LIMIT_RPM` (default: `100` requests/minute)
* `HRC_RATE_LIMIT_BACKEND`: `memory` (single node) or `redis` (multi-node or cluster).
* With the `redis` backend, Redis errors and timeouts reject non-exempt requests with HTTP 503 (fail-closed). Redis checks run off the API event loop.

### Monitoring and metrics

* `HRC_METRICS_ENABLED` (default: `false`). Enables `/metrics` for Prometheus.
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

### Cross-level state sync

* `HRC_CROSS_LEVEL_SYNC` (default: `true`)
* `HRC_CROSS_LEVEL_BATCH` (default: `100`)
* `HRC_CROSS_LEVEL_TIMEOUT` (default: `30.0` seconds)

### Integration

* `ERP_INTEGRATION_ENABLED` (`True`)
* `SUPPORTED_ERP_SYSTEMS` (list: `sap`, `oracle`, `microsoft_dynamics`)

### Logging

* `LOG_LEVEL` (default: `DEBUG` in dev, `DEBUG` in test, `WARNING` in production)
* `LOG_FORMAT` (standard Python logging format string).
* `HRC_LOG_FORMAT`: `text` (default) or `json` (for centralized logging like ELK/Loki).
* `HRC_LOG_SQL_DETAIL` (default: `false`)

### CLI

* `CLI_CONFIG_FILE` (default: `chains.json`)
* `CLI_LOG_LEVEL` (default: `INFO`)

## Example .env (development)

```dotenv
HRC_ENV=dev
HRC_API_HOST=0.0.0.0
HRC_API_PORT=2661
HRC_CONSENSUS_TYPE=proof_of_authority
HRC_AUTH_ENABLED=false
HRC_CORS_ALLOW_ALL=true
DATABASE_URL=postgresql://hiera:hiera@localhost:5432/hierachain
LOG_LEVEL=DEBUG
```

## Recommended production configuration (minimum)

```dotenv
HRC_ENV=production
HRC_API_HOST=0.0.0.0
HRC_AUTH_ENABLED=true
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=https://portal.example.com
HRC_RATE_LIMIT=true
DATABASE_URL=postgresql+psycopg://user:pass@db:5432/hierachain
HRC_STORAGE_BACKEND=redis
REDIS_HOST=redis
REDIS_PORT=6379
HRC_IPFS_ENABLED=true
HRC_IPFS_HOST=/ip4/ipfs/tcp/5001
HRC_IPFS_ENCRYPTION_KEY=your_32_byte_hex_key_here
```
