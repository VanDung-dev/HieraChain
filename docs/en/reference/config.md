---
title: "Configuration"
description: "Environment variables and settings in hierachain/config/settings.py; override methods and default values."
icon: material/tune
---

# System Configuration

## Purpose

This document lists the main configuration variables of HieraChain (read from environment variables and constants), defined in `hierachain/config/settings.py`, along with default values and usage recommendations.

## Scope

* Applies to runtime API/CLI and Sub-Chain/Main Chain components within the same Python process.
* Does not include infrastructure deployment parameters (k8s manifests, reverse proxy), only describes environment variables that HieraChain directly uses.

## Accessing Configuration in Code

```python
from hierachain.config.settings import settings

print(settings.API_HOST, settings.API_PORT)
print(settings.CONSENSUS_TYPE)
print(settings.AUTH_ENABLED)
```

## Environment Variables and Defaults (Main Groups)

### Runtime Environment

* `HRC_ENV`: configuration environment, values: `dev` (default) | `test` | `product`. Affects which configuration class is selected (Development/Testing/Production).

### API

* `HRC_API_HOST` (default: `localhost` in dev, `127.0.0.1` in production)
* `HRC_API_PORT` (default: `2661`)
* `API_VERSION` (constant: `v1`)

### Consensus/Blockchain

* `HRC_CONSENSUS_TYPE` (default: `proof_of_authority`; supported: `proof_of_authority`, `proof_of_federation`)
* `CONSENSUS_FEDERATION_CONFIG`: federation configuration (min_validators: 3, block_interval: 5.0)
* `VALIDATOR_TIMEOUT` (default: `30` seconds)
* `BFT_ENABLED` (default: `True`), `BFT_FAULT_TOLERANCE` (default: `1`), `BFT_NODE_COUNT` (default: `4`)
* Block limits: `BLOCK_SIZE_LIMIT` (default: `1000` events/block in dev, `10` in test)
* `PROOF_SUBMISSION_INTERVAL` (default: `300` seconds in dev, `10` in test)
* `HRC_VALIDATOR_IDENTITY`: validator identity file path (default: `validator_key.json`)

### Storage & Cache

* `HRC_STORAGE_BACKEND` (default: `sqlite` in dev, `memory` in test, `redis` in production; accepts: `memory|redis|sqlite`)
* `WORLD_STATE_CACHE_SIZE` (default: `1000`)
* Advanced caching: `ADVANCED_CACHING_ENABLED` (default: `True`)
* `BLOCK_CACHE_SIZE` (default: `5000`), `EVENT_CACHE_SIZE` (`20000`), `ENTITY_CACHE_SIZE` (`10000`)
* Cache policies: `BLOCK_CACHE_POLICY` (`lru`), `EVENT_CACHE_POLICY` (`ttl`), `ENTITY_CACHE_POLICY` (`lfu`)
* `ENTITY_TTL` (default: `3600` seconds)
* DB: `DATABASE_URL` (default: `sqlite:///hierachain.db`)
* Redis: `REDIS_HOST` (`localhost`), `REDIS_PORT` (`6379`), `REDIS_DB` (`0`)

### IPFS (Off-chain Storage)

* `HRC_IPFS_ENABLED` (default: `false`): Enable/disable IPFS integration for large data.
* `HRC_IPFS_HOST` (default: `/ip4/127.0.0.1/tcp/5001`): IPFS daemon API address.
* `HRC_IPFS_AUTO_PIN` (default: `true`): Automatically pin data after upload to prevent garbage collection.
* `HRC_IPFS_TIMEOUT` (default: `120` seconds): Maximum wait time for IPFS operations.
* `HRC_IPFS_ENCRYPTION_KEY`: AES-256 encryption key (32-byte hex). **Must** be identical across all Nodes in the same Channel/Organization.

### Parallel Processing & Resources

* `PARALLEL_PROCESSING_ENABLED` (`True`), `MAX_WORKERS` (`None` → auto 50% CPU cores), `PROCESSING_CHUNK_SIZE` (`100`)
* DoS protection: `HRC_EVENT_POOL_MAX_SIZE` (default: `10000`), `HRC_RAM_CRITICAL_THRESHOLD` (`95.0` %)

### Security & Authentication

* Authentication: `HRC_AUTH_ENABLED` (`false` in dev/test; `True` enforced in production)
* `HRC_API_KEY_LOCATION` (`header`), `HRC_API_KEY_NAME` (`X-API-Key`)
* Secret Backend: `HRC_SECRET_BACKEND` (values: `env` | `vault` | `aws`). Default is `env`.
* Master Key: `HRC_MASTER_KEY_SOURCE` (`auto` in dev/test, `env` in production), `HRC_MASTER_KEY_FILE` (default: `config/master_backup_key.key`)
* Brute-force protection:
    * `HRC_BF_MAX_FAILURES` (default: `5`)
    * `HRC_BF_LOCKOUT_SECONDS` (default: `900` = 15 minutes)
    * `HRC_BF_WINDOW_SECONDS` (default: `300` = 5 minutes)
* Identity & Organization: `IDENTITY_MANAGER_ENABLED` (`True`), `REQUIRE_ORGANIZATION_VALIDATION` (`True`), `MSP_ENABLED` (`True`)

### P2P Network Security

* `HRC_P2P_TRUST_POLICY` (default: `open` in dev, `strict` in production; values: `open|strict`)
* `HRC_P2P_PEER_ALLOWLIST` (comma-separated peer IDs list for strict mode)
* `HRC_P2P_REQUIRE_SIGNATURES` (`false` in dev, `true` in production)

### CORS

* `HRC_CORS_ALLOW_ALL` (`true` in dev, `false` in production)
* `HRC_CORS_ORIGINS` (CSV domain string; production requires explicit specification)
* `CORS_ALLOW_METHODS` (list of allowed methods)
* `CORS_ALLOW_HEADERS` (list of allowed headers)

### HTTPS/HSTS

* `HRC_HSTS_ENABLED` (`false` in dev/test; `true` in production)
* `HRC_HSTS_MAX_AGE` (default: `31536000` = 1 year)

### Rate Limiting

* `HRC_RATE_LIMIT` (`false` in dev/test; `true` in production)
* `HRC_RATE_LIMIT_RPM` (default: `100` requests/minute)
* `HRC_RATE_LIMIT_BACKEND`: `memory` (single node) or `redis` (multi-node/cluster).

### Monitoring & Metrics

* `HRC_METRICS_ENABLED` (default: `false`): Enable `/metrics` endpoint for Prometheus.
* `HRC_TRUSTED_PROXIES` (default: `127.0.0.1`): List of trusted Reverse Proxy IPs (for HTTP/2, HTTP/3).

### Multi-Organization

* `MULTI_ORG_ENABLED` (`True`), `MSP_ENABLED` (`True`)
* `ORGANIZATION_ADMIN_THRESHOLD` (default: `1`)
* `CHANNEL_CREATION_POLICY` (default: `majority`; values: `majority|unanimous|admin_only`)
* `AFFILIATION_HIERARCHY_ENABLED` (`True`)

### Zero-Knowledge (ZK)

* `HRC_ENABLE_ZK_PROOFS` (default: `false`)
* `HRC_ZK_MODE` (`mock` or `production`, default `mock`)
* `HRC_ZK_VERIFICATION_KEY`, `HRC_ZK_PROVING_KEY`, `HRC_ZK_CIRCUIT` (file paths)
* `HRC_ZK_REQUIRED_MAINCHAIN` (default: `false`)

### Kubernetes (Sub-Chain namespace isolation)

* `HRC_K8S_ENABLED` (default: `false`)
* `HRC_K8S_NAMESPACE_PREFIX` (default: `hrc-subchain-`)
* `HRC_K8S_CONFIG` (kubeconfig path, empty if in-cluster)
* Limits/resources:

    * `HRC_K8S_CPU_LIMIT` (default: `1000m`)
    * `HRC_K8S_MEMORY_LIMIT` (default: `1Gi`)
    * `HRC_K8S_CPU_REQUEST` (default: `250m`)
    * `HRC_K8S_MEMORY_REQUEST` (default: `256Mi`)

### Proof Aggregation

* `HRC_PROOF_AGGREGATION` (default: `true`)
* `HRC_PROOF_BATCH_SIZE` (default: `10`)
* `HRC_PROOF_BATCH_TIMEOUT` (default: `30.0` seconds)
* `HRC_PROOF_COMPRESSION` (default: `true`)

### Sub-chain Rebalancing

* `HRC_REBALANCE_ENABLED` (default: `true`)
* `HRC_REBALANCE_THRESHOLD_EPS` (default: `1000` events/sec)
* `HRC_REBALANCE_CHECK_INTERVAL` (default: `60.0` seconds)
* `HRC_REBALANCE_MIN_EVENTS` (default: `5000` events before split)
* `HRC_REBALANCE_COOLDOWN` (default: `300.0` seconds = 5 minutes)

### Cross-level State Sync

* `HRC_CROSS_LEVEL_SYNC` (default: `true`)
* `HRC_CROSS_LEVEL_BATCH` (default: `100`)
* `HRC_CROSS_LEVEL_TIMEOUT` (default: `30.0` seconds)

### Integration

* `ERP_INTEGRATION_ENABLED` (`True`)
* `SUPPORTED_ERP_SYSTEMS` (list: `sap`, `oracle`, `microsoft_dynamics`)

### Logging

* `LOG_LEVEL` (default: `INFO` in dev, `DEBUG` in test, `WARNING` in production)
* `LOG_FORMAT` (standard Python logging format string).
* `HRC_LOG_FORMAT`: `text` (default) or `json` (for centralized logging like ELK/Loki).
* `HRC_LOG_SQL_DETAIL` (default: `true` in dev, `false` in production)

### CLI

* `CLI_CONFIG_FILE` (default: `chains.json`)
* `CLI_LOG_LEVEL` (default: `INFO`)

## Example .env (Development)

```dotenv
HRC_ENV=dev
HRC_API_HOST=0.0.0.0
HRC_API_PORT=2661
HRC_CONSENSUS_TYPE=proof_of_authority
HRC_AUTH_ENABLED=false
HRC_CORS_ALLOW_ALL=true
DATABASE_URL=sqlite:///hierachain.db
LOG_LEVEL=DEBUG
```

## Recommended Production Configuration (Minimum)

```dotenv
HRC_ENV=product
HRC_API_HOST=0.0.0.0
HRC_AUTH_ENABLED=true
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=https://portal.example.com
HRC_RATE_LIMIT=true
DATABASE_URL=postgresql+psycopg://user:pass@db:5432/hierachain
DEFAULT_STORAGE_BACKEND=redis
REDIS_HOST=redis
REDIS_PORT=6379
HRC_IPFS_ENABLED=true
HRC_IPFS_HOST=/ip4/ipfs/tcp/5001
HRC_IPFS_ENCRYPTION_KEY=your_32_byte_hex_key_here
```
