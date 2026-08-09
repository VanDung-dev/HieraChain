# AGENT.md — HieraChain Coding Agent Reference

> **Purpose**: High-density system constraints, architectural map, and key entry points for AI coding agents working on HieraChain.

---

## Modular Rules Reference

Specific rules are modularized under `.agents/rules/` for targeted evaluation:
* [01-forbidden-terms.md](file:///.agents/rules/01-forbidden-terms.md) — Cryptocurrency term censorship & coding conventions
* [02-architecture-rules.md](file:///.agents/rules/02-architecture-rules.md) — Plugin layer philosophy & design patterns
* [03-changelog-rules.md](file:///.agents/rules/03-changelog-rules.md) — Scope rules for `docs/en/changelog.md` and `docs/vi/changelog.md`
* [04-documentation-sync-rules.md](file:///.agents/rules/04-documentation-sync-rules.md) — Code-backed accuracy & 1:1 EN/VI documentation parity rules

---

## Core Architecture & Reference Entries

### 1. Event Model (Not Transaction Model)
Every operation submits an event dict with the following shape:
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

### 2. Core Primitives
* **Blockchain**: Base chain implementation storing events in blocks with Merkle tree proofs.
* **World State**: Tracks current entity states from finalized blocks for fast queries.
* **Merkle Tree**: Builds cryptographic proofs of event inclusion for tamper evidence.

### 3. Two-Tier Hierarchy
* **Main Chain**: Stores only cryptographic proofs/hashes from Sub-Chains.
* **Sub-Chains**: Store domain-specific events, submitting proof hashes up to the Main Chain via `HierarchyManager`.

### 4. Distributed Security Architecture

| Module | Security Responsibilities |
|--------|--------------------------|
| `hierachain/api/` | Security headers, rate limiting, payload limits, API key auth, CORS |
| `hierachain/api/storage/` | AES-256-GCM encryption for IPFS data |
| `hierachain/network/` | Curve25519 transport, Ed25519 message signing, MSP certificates, replay protection |
| `hierachain/consensus/` | BFT cryptographic operations, ZK proofs, block signatures |
| `hierachain/security/` | Identity, key management, policy engine, sanitization, brute force protection |
| `hierachain/cluster/` | HMAC-SHA256 for cluster lockdown, encrypted rollback snapshots |
| `hierachain/error_mitigation/` | Audit logging, integrity verification |

### 5. Key Classes & Entry Points

| Task | Class / Function | File |
|------|-----------------|------|
| Submit business event | `SubChain.add_event()` | [hierarchical/sub_chain/base.py](./hierachain/hierarchical/sub_chain/base.py) |
| Manage all chains | `HierarchyManager` | [hierarchical/hierarchy_manager/base.py](./hierachain/hierarchical/hierarchy_manager/base.py) |
| Order events → blocks | `OrderingService.receive_event()` | [consensus/ordering/service.py](./hierachain/consensus/ordering/service.py) |
| Policy enforcement | `PolicyEngine.evaluate()` | [security/policy_engine.py](./hierachain/security/policy_engine.py) |
| Trace entity across chains | `EntityTracer.trace_entity()` | [domains/utils/entity_tracer.py](./hierachain/domains/utils/entity_tracer.py) |
| Validate system integrity | `CrossChainValidator.validate_system_integrity()` | [domains/utils/cross_chain_validator.py](./hierachain/domains/utils/cross_chain_validator.py) |
| Core blockchain operations | `Blockchain` | [core/blockchain.py](./hierachain/core/blockchain.py) |
| Merkle tree proofs | `MerkleTree` | [core/merkle_tree.py](./hierachain/core/merkle_tree.py) |
| Entity state tracking | `WorldState.get_entity_state()` | [state/world_state.py](./hierachain/state/world_state.py) |
| Real-time streaming | `WebSocketManager` (singleton `ws_manager`) | [api/websocket/manager.py](./hierachain/api/websocket/manager.py) |
| Store to IPFS (encrypted) | `IPFSClient.upload_json()` | [api/storage/ipfs_client.py](./hierachain/api/storage/ipfs_client.py) |
| Assess system risks | `RiskAnalyzer.perform_comprehensive_analysis()` | [risk_management/risk_analyzer.py](./hierachain/risk_management/risk_analyzer.py) |

### 6. Full Module Directory

| Package | Purpose |
|---------|---------|
| `adapters/` | Database adapters (SQLite, Redis) |
| `api/` | REST, GraphQL, WebSocket APIs |
| `cli/` | Command-line interface |
| `cluster/` | Cluster lockdown, rollback snapshots |
| `config/` | Environment, secrets, version, settings |
| `consensus/` | Ordering, BFT, ZK proofs |
| `core/` | Block, Blockchain, Merkle tree primitives |
| `domains/` | Generic & traceability domain logic |
| `error_mitigation/` | Audit logging, integrity verification |
| `hierarchical/` | MainChain, SubChain, HierarchyManager |
| `integration/` | ERP, enterprise adapters |
| `monitoring/` | Metrics, alerting, performance monitoring |
| `network/` | Transport, messaging, MSP |
| `risk_management/` | Risk analysis, audit logging |
| `sdk/` | Async & sync client libraries |
| `security/` | Identity, key management, policy engine |
| `state/` | World state tracking |

---

## Behavioral Guidelines

Behavioral guidelines to reduce common LLM coding mistakes:

### 1. Think Before Coding
* State assumptions explicitly. Surface ambiguity early.
* Recommend simpler alternatives if an over-engineered approach is requested.

### 2. Simplicity First
* Minimum code that solves the problem. No speculative abstractions.
* If a 50-line solution works, do not write 200 lines.

### 3. Surgical Changes
* Touch only lines related to the request. Match existing formatting and code style.
* Clean up unused imports/variables created by your changes, but leave pre-existing code untouched.

### 4. Goal-Driven Execution
* Define verifiable success criteria before editing. Verify with unit tests or builds.

---

## Related Documentation
* [CODEBASE_REFERENCE.md](./docs/CODEBASE_REFERENCE.md) — Detailed architecture reference (packages, design patterns, data flows, full directory layout).
* [DEV_GUIDE.md](./docs/DEV_GUIDE.md) — Full developer guide with environment setup, running tests, benchmarks, and scripts.
* [ARCHITECTURE.md](./docs/ARCHITECTURE.md) — Visual architecture diagrams, Rust integration layers, and ZKP concepts.
* [workflows/overview.md](docs/en/workflows/overview.md) — Comprehensive guide to 16 system workflows including event submission, consensus, security, and recovery.
