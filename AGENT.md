# AGENT.md — HieraChain Coding Agent Reference

> **Purpose**: Context document for AI coding agents working on the HieraChain codebase.
> This document describes the project architecture, development workflow, conventions, and constraints that agents must follow.

---

## What is HieraChain?

HieraChain is an **enterprise-grade hierarchical blockchain ledger** built in Python. It is designed for **business process management** — NOT cryptocurrency. Key philosophy:

- All operations are called **"events"** (not "transactions")
- No cryptocurrency concepts: no mining, no tokens, no wallets, no coins
- Hierarchical two-tier structure (Main Chain + Sub-Chains) mirrors enterprise org charts
- Built for ERP integration (SAP, Oracle, Dynamics)

> **Critical rule**: Never introduce cryptocurrency terminology into the codebase. The `CrossChainValidator` literally scans for and flags forbidden terms: `transaction`, `mining`, `coin`, `token`, `wallet`, `address`, `sender`, `receiver`, `amount`, `fee`.

---

## Repository Layout

```
HieraChain/
├── hierachain/               # Main package
│   ├── core/                 # Block, Blockchain, Caching, DomainContract, ParallelEngine
│   ├── hierarchical/         # MainChain, SubChain, Channel, HierarchyManager, K8sNamespaceManager, Rebalancer
│   ├── consensus/
│   │   ├── ordering/         # OrderingService (Facade) + 10 sub-components
│   │   └── bft/              # BFTConsensus, BFTViewChangeManager, cryptographic, network
│   ├── cluster/              # ClusterManager, ClusterLockdownManager, StateSyncManager
│   ├── monitoring/           # AlertManager, PerformanceMonitor
│   ├── risk_management/      # RiskAnalyzer, MitigationStrategies, AuditLogger
│   ├── security/
│   │   ├── verify/           # BlockVerifier, SignatureVerifier, APIKeyVerifier, ZKVerifier
│   │   └── (identity, msp, key_manager, policy_engine, zk_prover, ...)
│   ├── network/              # ZmqTransport, SecureConnection, PeerTrustManager
│   ├── storage/              # WorldState, SqlBackend, MemoryStorage, Models
│   ├── adapters/
│   │   └── storage/          # RedisStorageAdapter, FileStorageAdapter, SQLiteAdapter
│   ├── error_mitigation/     # Journal, RecoveryEngine, RollbackManager, ErrorClassifier, Validator
│   ├── integration/          # EnterpriseIntegration, ArrowClient, erp_adapters/
│   ├── domains/
│   │   └── generic/
│   │       ├── chains/       # BaseChain, DomainChain (with 2PC + business rules)
│   │       ├── events/       # BaseEvent, DomainEvent factory functions
│   │       └── utils/        # EntityTracer, CrossChainValidator
│   ├── api/
│   │   ├── server.py         # FastAPI entrypoint
│   │   ├── blockchain_explorer.py
│   │   ├── graphql/          # GraphQL schema
│   │   ├── websocket/        # WebSocketManager, registry, subscriptions, handlers, builders
│   │   ├── storage/          # IPFSClient (AES-256-GCM), encryption, helpers
│   │   ├── v1/, v2/, v3/     # Versioned REST endpoints + schemas
│   │   └── (middleware, dependencies, ...)
│   ├── sdk/                  # Python client (retry + circuit breaker)
│   ├── cli/                  # Click CLI (chain, event, node commands)
│   ├── config/               # Settings singleton, env_manager, logging config
│   └── units/                # Semantic versioning
├── tests/
│   ├── unit/                 # Unit tests per module
│   ├── integration/          # Integration tests
│   ├── scenarios/            # End-to-end scenarios
│   └── stress/               # Stress/benchmark tests
├── demo/                     # Demo scripts
├── scripts/                  # Dev utilities (static analysis, benchmarks)
├── docker/                   # Dockerfile, docker-compose, k8s manifests
├── requirements.txt
├── requirements_dev.txt
└── pyproject.toml
```

---

## Environment Setup

**Python versions supported**: 3.10, 3.11, 3.12, 3.13

```bash
# Create and activate venv (macOS/Linux)
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
pip install -r requirements_dev.txt
pip install -e .          # install package in dev/editable mode
```

---

## Running the Project

```bash
# Start API server
python -m hierachain.api.server
# → FastAPI server at http://localhost:2661
# → Docs: http://localhost:2661/docs
# → ReDoc: http://localhost:2661/redoc

# Run CLI
python -m hierachain chain list
python -m hierachain chain create supply_chain --name my_chain
```

---

## Running Tests

> ⚠️ **WARNING**: Do NOT run all tests at once — use per-file execution to avoid resource conflicts.

```bash
# Unit tests
python -m pytest tests/unit -v

# Integration tests
python -m pytest tests/integration -v

# Scenario tests
python -m pytest tests/scenarios -v

# Run a single test file (recommended)
python -m pytest tests/unit/test_blockchain.py -v

# Benchmarks only
python -m pytest tests --benchmark-only -v --benchmark-save=benchmark_report

# All tests (use with caution)
python -m pytest tests -v
```

### Docker Stress Testing

```bash
# Run stress tests (4 nodes, 1 CPU + 1GiB RAM each)
docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester \
  python -m pytest tests/stress/ -v \
  --html=/app/log/report/stress_test_report.html --self-contained-html

# Cleanup
docker compose -f docker/docker-compose.test.yml down --remove-orphans
```

Reports saved to `log/report/`.

---

## Developer Scripts

```bash
# Static analysis
python -m scripts.static_analysis
python -m scripts.static_analysis --format text
python -m scripts.static_analysis --output analysis_report.json

# Benchmarks
python scripts/benchmark_hashing.py
python scripts/benchmark_throughput.py --events 1000 --workers 4 --batch-size 100

# Verify storage persistence
python scripts/verify_storage.py

# Clean demo data
rm -rf demo/data demo/hierachain.db 2>/dev/null
```

---

## Key Architecture Concepts Agents Must Know

### 1. Event Model (not Transaction Model)

Every operation submits an **event dict** with this shape:

```python
event = {
    "entity_id": "product-123",     # metadata identifier (NOT a user address)
    "event": "quality_check",        # event type string
    "timestamp": time.time(),
    "details": {                     # domain-specific payload
        "check_type": "visual",
        "check_result": "passed"
    }
}
```

**Never use**: `transaction`, `sender`, `receiver`, `amount`, `wallet`, `fee`, `mining`.

### 2. Two-Tier Hierarchy

```
Main Chain  →  stores only proofs from Sub-Chains (NOT raw events)
Sub-Chains  →  store domain-specific events, submit proof hashes up
```

Interaction entry point: `HierarchyManager` in `hierarchical/hierarchy_manager.py`.

### 3. Consensus (pluggable via `HRC_CONSENSUS_TYPE`)

| Value | Mechanism | Use case |
|-------|-----------|----------|
| `proof_of_authority` | Designated authority signs blocks | Default, business |
| `proof_of_federation` | Rotating leader: `Leader = Validators[height % n]` | Consortium |
| `byzantine_fault_tolerant` | 3-phase PBFT, requires `n >= 3f+1` | Critical systems |

### 4. Storage Backends (pluggable via `HRC_STORAGE_BACKEND`)

| Value | Class | Notes |
|-------|-------|-------|
| `sqlite` | `SQLiteAdapter` | Default, dev-friendly |
| `redis` | `RedisStorageAdapter` | O(log n) entity index via sorted sets |
| `memory` | `MemoryStorage` | Testing only |

### 5. Key Classes & Entry Points

| Task | Class / Function | File |
|------|-----------------|------|
| Submit business event | `SubChain.add_event()` | `hierarchical/sub_chain.py` |
| Manage all chains | `HierarchyManager` | `hierarchical/hierarchy_manager.py` |
| Order events → blocks | `OrderingService.receive_event()` | `consensus/ordering/service.py` |
| Policy enforcement | `PolicyEngine.evaluate()` | `security/policy_engine.py` |
| Trace entity across chains | `EntityTracer.trace_entity()` | `domains/generic/utils/entity_tracer.py` |
| Validate system integrity | `CrossChainValidator.validate_system_integrity()` | `domains/generic/utils/cross_chain_validator.py` |
| Real-time streaming | `WebSocketManager` (singleton: `ws_manager`) | `api/websocket/manager.py` |
| Store to IPFS (encrypted) | `IPFSClient.upload_json()` | `api/storage/ipfs_client.py` |
| Assess system risks | `RiskAnalyzer.perform_comprehensive_analysis()` | `risk_management/risk_analyzer.py` |

---

## Configuration (Environment Variables)

All configs live in `hierachain/config/settings.py` as a singleton `settings`. Override via env vars:

| Variable | Purpose | Default |
|----------|---------|---------|
| `HRC_CONSENSUS_TYPE` | Consensus mechanism | `proof_of_authority` |
| `HRC_STORAGE_BACKEND` | Storage backend | `sqlite` |
| `HRC_ENABLE_ZK_PROOFS` | ZK proof verification | `false` |
| `HRC_AUTH_ENABLED` | API authentication | `false` |
| `HRC_CLUSTER_SECRET` | HMAC secret for cluster lockdown | _(required in cluster mode)_ |
| `HRC_SMTP_USERNAME` / `HRC_SMTP_PASSWORD` | Email alert credentials | _(optional)_ |
| `HRC_IPFS_HOST` | IPFS daemon address | `/ip4/127.0.0.1/tcp/5001` |
| `HRC_IPFS_ENCRYPTION_KEY` | AES-256 key for IPFS data | _(auto-generated if missing)_ |
| `DATABASE_URL` | DB connection string | `sqlite:///hierachain.db` |

---

## Coding Conventions

### Python Style
- **Type hints required** on all function signatures (the codebase enforces this)
- Use `dataclasses` and `Enum` for structured data (see `consensus/bft/types.py` as reference)
- Module-level helper functions preferred over deeply nested methods (see `bft/consensus.py`)
- Logging via `logging.getLogger(__name__)` — never `print()` in library code
- Use `hierachain.security.secure_logging.SecureLogger` for security-sensitive modules

### Architecture Patterns (follow existing conventions)
- **Facade Pattern**: complex subsystems expose a single coordinator class — see `OrderingService`, `HierarchyManager`
- **Strategy Pattern**: swappable algorithms (cache policies, consensus, split strategies)
- **State Machine**: lifecycle transitions must follow defined allowed states — see `DomainContract` lifecycle, `ClusterLockdownManager`
- **Repository Pattern**: never access DB directly from business logic — use storage adapters
- **Adapter Pattern**: new storage backends go in `adapters/storage/`, new ERP integrations in `integration/erp_adapters/`

### Module Organization
- Each sub-package exposes a clean `__init__.py` with `__all__` and categorized imports
- See `hierachain/risk_management/__init__.py` and `hierachain/security/__init__.py` as canonical examples
- New verifiers belong in `security/verify/`
- New domain-agnostic utilities belong in `domains/generic/utils/`

---

## Forbidden Patterns

- ❌ No cryptocurrency terminology in any event data, variable names, or comments
- ❌ No direct `sqlite3` or `redis` calls outside `adapters/storage/`
- ❌ No `print()` statements in library code (use logging)
- ❌ Do NOT run all tests at once — run per-file
- ❌ Do NOT store secrets in code — use environment variables
- ❌ Do NOT skip the `TransactionJournal` durability step when implementing new ordering flows
- ❌ Do NOT bypass `PolicyEngine` for access-sensitive operations

---

## Demos

```bash
# Core features (hierarchical chains, MSP, channels, private data)
python demo/demo.py

# Key backup and recovery
python demo/demo_key_backup.py

# BFT consensus over ZeroMQ
python demo/demo_zmq_consensus.py
```

---

## Related Documents

- [`docs/CODEBASE_REFERENCE.md`](./docs/CODEBASE_REFERENCE.md) — Detailed architecture reference (all packages, design patterns, data flows)
- [`docs/DEV_GUIDE.md`](./docs/DEV_GUIDE.md) — Full developer guide with environment setup and testing
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — Visual high-level architecture (Mermaid diagrams, Rust layer, ZKP)
- [`docs/`](./docs/) — All developer documentation
