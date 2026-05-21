# AGENT.md — HieraChain Coding Agent Reference

> **Purpose**: High-density system constraints, architectural rules, and coding conventions for AI coding agents working on HieraChain.

---

## Critical Guardrails & Terminology Rules

HieraChain is an **enterprise-grade hierarchical blockchain ledger** built in Python for business processes — **NOT cryptocurrency**.

* **Term Censorship**: Never introduce cryptocurrency terminology into any event data, variable names, API endpoints, or comments.
* **Forbidden terms**: `transaction`, `mining`, `coin`, `token`, `wallet`, `address`, `sender`, `receiver`, `amount`, `fee`.
* **Required terms**: Use `event` (instead of transaction), `node`, `msp_id`, `entity_id`, etc.
* *Note*: The `CrossChainValidator` scans and flags forbidden terms on commit/validation.

---

## Plugin Layer Philosophy (No Over-Engineering)

HieraChain is designed as a **Plugin Layer** for existing enterprise Web2 infrastructure, not a standalone network application.

* **Do NOT implement**: Internal TLS/SSL handling, WAF, firewalls, network filtering, or transport-level certificate management. These layers already exist in the Web2 enterprise reverse proxy/API Gateway.
* **Focus on blockchain value**: Focus exclusively on Immutability, Distributed Trust, Tamper Evidence, and Non-repudiation.
* **Python Latency Constraint**: Keep code minimal and fast (~10-20ms base latency). Avoid adding internal encryption layers or mTLS that add unnecessary CPU/latency overhead.

---

## Distributed Security Architecture

Security in HieraChain is **distributed across multiple modules** rather than isolated in `security/`. When modifying or analyzing security, check the appropriate layer:

| Module | Security Responsibilities |
|--------|--------------------------|
| `hierachain/api/` | Security headers, rate limiting, payload limits, API key auth, CORS |
| `hierachain/api/storage/` | AES-256-GCM encryption for IPFS data |
| `hierachain/network/` | Curve25519 transport, Ed25519 message signing, MSP certificates, replay protection |
| `hierachain/consensus/` | BFT cryptographic operations, ZK proofs, block signatures |
| `hierachain/security/` | Identity, key management, policy engine, sanitization, brute force protection |
| `hierachain/cluster/` | HMAC-SHA256 for cluster lockdown, encrypted rollback snapshots |
| `hierachain/error_mitigation/` | Audit logging, integrity verification |

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

### 2. Two-Tier Hierarchy
* **Main Chain**: Stores only cryptographic proofs/hashes from Sub-Chains.
* **Sub-Chains**: Store domain-specific events, submitting proof hashes up to the Main Chain via `HierarchyManager`.

### 3. Key Classes & Entry Points

| Task | Class / Function | File |
|------|-----------------|------|
| Submit business event | `SubChain.add_event()` | [hierarchical/sub_chain.py](./hierachain/hierarchical/sub_chain.py) |
| Manage all chains | `HierarchyManager` | [hierarchical/hierarchy_manager.py](./hierachain/hierarchical/hierarchy_manager.py) |
| Order events → blocks | `OrderingService.receive_event()` | [consensus/ordering/service.py](./hierachain/consensus/ordering/service.py) |
| Policy enforcement | `PolicyEngine.evaluate()` | [security/policy_engine.py](./hierachain/security/policy_engine.py) |
| Trace entity across chains | `EntityTracer.trace_entity()` | [domains/generic/utils/entity_tracer.py](./hierachain/domains/generic/utils/entity_tracer.py) |
| Validate system integrity | `CrossChainValidator.validate_system_integrity()` | [domains/generic/utils/cross_chain_validator.py](./hierachain/domains/generic/utils/cross_chain_validator.py) |
| Real-time streaming | `WebSocketManager` (singleton `ws_manager`) | [api/websocket/manager.py](./hierachain/api/websocket/manager.py) |
| Store to IPFS (encrypted) | `IPFSClient.upload_json()` | [api/storage/ipfs_client.py](./hierachain/api/storage/ipfs_client.py) |
| Assess system risks | `RiskAnalyzer.perform_comprehensive_analysis()` | [risk_management/risk_analyzer.py](./hierachain/risk_management/risk_analyzer.py) |

---

## Coding Conventions & Forbidden Patterns

### Python & Design Style
* **Strict Type Hints**: Required on all function signatures across the codebase.
* **Module-level Helpers**: Preferred over deeply nested helper methods.
* **Facade Pattern**: Complex subsystems must expose a single coordinator class (e.g., `OrderingService`, `HierarchyManager`).
* **Strategy Pattern**: Use for swappable algorithms (consensus, caching, splitting).
* **Repository Pattern**: Never access DB directly from business logic; use storage adapters under `adapters/storage/`.
* **State Machine**: Lifecycle transitions must follow defined allowed states (e.g., `DomainContract` lifecycle).

### Forbidden Patterns
* **No Cryptocurrency Terminology**: Do not use crypto terms in event data, variable names, or comments.
* **No Direct Storage Calls**: Do not make direct `sqlite3` or `redis` calls outside of `adapters/storage/`.
* **No `print()` Statements**: Do not use `print()` in library code (use logging or `SecureLogger`).
* **No Bulk Test Execution**: Do not run all tests at once to avoid resource conflicts; run per-file.
* **No Hardcoded Secrets**: Do not store secrets in code; use environment variables.
* **No Skipping Transaction Journal**: Do not skip the `TransactionJournal` durability step when implementing ordering flows.
* **No Bypassing Policy Engine**: Do not bypass `PolicyEngine` for access-sensitive operations.

---

## Behavioral Guidelines (CLAUDE.md Principles)

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Related Documentation
* [CODEBASE_REFERENCE.md](./docs/CODEBASE_REFERENCE.md) — Detailed architecture reference (packages, design patterns, data flows, full directory layout).
* [DEV_GUIDE.md](./docs/DEV_GUIDE.md) — Full developer guide with environment setup, running tests, benchmarks, and scripts.
* [ARCHITECTURE.md](./docs/ARCHITECTURE.md) — Visual architecture diagrams, Rust integration layers, and ZKP concepts.
* [workflows/index.md](docs/en/workflows/overview.md) — Comprehensive guide to 16 system workflows including event submission, consensus, security, and recovery.
