---
title: "Fault-tolerance & Integrity"
description: "Actual resource protection and integrity checks in HieraChain (no separate Resource Guard/Integrity module)."
icon: material/shield-check
---

# Fault-tolerance & Integrity

This page previously described `security/resource_guard.py` and `security/integrity.py`, which do not exist in `hierachain/`. Fault tolerance in the codebase is distributed instead.

## Resource protection (actual)

* Rate and payload limits live in `hierachain/api/middleware.py` (`add_rate_limit`, `add_payload_limit` with `HRC_RATE_LIMIT`, `HRC_RATE_LIMIT_RPM`, `HRC_RATE_LIMIT_BACKEND`, `HRC_TRUSTED_PROXIES`; payload is checked via `request.stream()` with a 1MB limit).
* Event pool and RAM guards are `HRC_EVENT_POOL_MAX_SIZE` (10k) and `HRC_RAM_CRITICAL_THRESHOLD` (95%), checked in ordering and storage paths.
* There is no `ResourceGuardMiddleware`. The 70%/90% threshold table and the load shedding in `monitoring/performance_monitor.py` described earlier were fabricated. Use app middleware together with reverse proxy limits.

## Integrity checks (actual)

There is no startup signature scan in `security/integrity.py`. The actual integrity mechanisms are:

* Merkle and chain links in `hierachain/core/block.py` and `core/merkle_tree.py` (domain-separated `0x01` prefix) and `consensus/ordering/storage.py:_verify_chain_links()` (`previous_hash` chain).
* Proof verification in `hierachain/hierarchical/main_chain/proofs.py:_verify_proof_in_main_chain` (fallback chain scan) and `security/verify/block_verifier.py`.
* Runtime integrity checks use chain links, Merkle roots, proof verification, and consensus validation. State snapshots and rollback are deployment responsibilities.

```mermaid
graph LR
    A[Block finalize] --> B[previous_hash check]
    B --> C[Merkle root verify]
    C --> D[Proof verify on MainChain]
    D --> E[Operational recovery if needed]
```

---

## Related

*   [Error Mitigation](../modules/error-mitigation.md)
*   [Monitoring](../modules/monitoring.md)
*   [Secure Logging](./lockdown-logging.md)
