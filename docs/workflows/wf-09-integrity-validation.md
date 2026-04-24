# WF-9: System Integrity Validation

**Group**: D — Data Integrity & Traceability
**Trigger**: Periodic monitoring schedule, manual operator call, or anomaly detection in WF-13
**Output**: `IntegrityReport` with overall status (`HEALTHY` / `DEGRADED`) and per-chain details
**Key modules**: `hierarchical/hierarchy_manager.py`, `security/verify/block_verifier.py`, `domains/generic/utils/cross_chain_validator.py`

> [← WF-8: Chain Rehydration](./wf-08-chain-rehydration.md) · [Back to Overview](../ARCHITECTURE.md) · [WF-10: Policy Enforcement →](./wf-10-policy-enforcement.md)

---

## Overview

A system-wide integrity check that validates the **cryptographic consistency** of all chains and verifies that the proofs stored on the Main Chain match the latest blocks on each Sub-Chain. This is the primary mechanism for **tamper detection** and **audit compliance**.

The check runs three parallel validation layers: Main Chain cryptographic validity, Sub-Chain cryptographic validity, and proof consistency between the two tiers.

---

## Flow Diagram

```mermaid
flowchart TB
    TRIGGER["🔍 Trigger\nvalidate_cross_chain_consistency()\nor get_system_integrity_report()"]

    subgraph Validation["Validation Layers (parallel)"]
        direction TB
        MC_VAL["🔗 Main Chain\nBlockVerifier.verify_chain()\nis_chain_valid()"]
        SC_VAL["📦 All Sub-Chains\nBlockVerifier.verify_chain()\nis_chain_valid()"]
        PROOF["📋 Proof Consistency\n_compute_proof_consistency()\nLatest SubChain block.hash\n== MainChain latest_proofs[name]"]
    end

    REPORT["📊 System Integrity Report"]
    HEALTHY["✅ HEALTHY\nAll chains valid\nAll proofs consistent"]
    DEGRADED["⚠️ DEGRADED\nChain invalid OR\nProof missing/mismatch"]
    ALERT["🚨 Alert via WF-13"]

    TRIGGER --> MC_VAL
    TRIGGER --> SC_VAL
    TRIGGER --> PROOF

    MC_VAL --> REPORT
    SC_VAL --> REPORT
    PROOF --> REPORT

    REPORT --> HEALTHY
    REPORT --> DEGRADED --> ALERT
```

---

## Tamper Detection Flow

```mermaid
sequenceDiagram
    autonumber
    participant OP as 👤 Operator / Monitor
    participant HM as 🏛️ HierarchyManager
    participant BV as 🔍 BlockVerifier
    participant CCV as 🛡️ CrossChainValidator

    OP->>HM: validate_cross_chain_consistency()
    HM->>BV: verify_chain(main_chain.chain)
    BV->>BV: For each block: hash(prev_block) == block.previous_hash?
    BV-->>HM: { valid: True/False, tampered_blocks: [] }

    loop Each Sub-Chain
        HM->>BV: verify_chain(sub_chain.chain)
        BV-->>HM: { valid: True/False }
        HM->>HM: _compute_proof_consistency(sub_chain_name)
        Note right of HM: sub_chain.latest_block.hash == main_chain.proofs[name]
    end

    HM->>CCV: validate_system_integrity()
    CCV->>CCV: Scan all events for forbidden crypto terms
    CCV-->>HM: { issues: [], forbidden_found: [] }

    HM-->>OP: IntegrityReport { overall_status, per_chain, proof_consistency, issues }
```

---

## Integrity Report Structure

```python
{
    "timestamp": 1714000000.0,
    "overall_status": "HEALTHY",          # or "DEGRADED"
    "system_overview": {
        "total_sub_chains": 3,
        "total_sub_chain_blocks": 142,
        "total_sub_chain_events": 3580,
        "system_uptime": 86400.0
    },
    "main_chain": {
        "valid": True,
        "height": 47
    },
    "sub_chains": {
        "supply_chain": {"valid": True, "height": 61},
        "logistics":    {"valid": True, "height": 48},
        "finance":      {"valid": True, "height": 33}
    },
    "proof_consistency": {
        "supply_chain": {
            "consistent": True,
            "latest_proof_hash": "a3f8b2...",
            "chain_height": 61
        }
    },
    "issues": []
}
```

---

## Step-by-Step Breakdown

| Step | Description |
|:-----|:------------|
| **1. Trigger** | Periodic timer, operator call, or WF-13 anomaly detection |
| **2. Main Chain verify** | `BlockVerifier.verify_chain()` recomputes every block hash and checks `previous_hash` linkage |
| **3. Sub-Chain verify** | Same verification applied to all registered Sub-Chains in parallel |
| **4. Proof consistency** | Compares `sub_chain.latest_block.hash` with `main_chain.proofs[chain_name]` |
| **5. Forbidden term scan** | `CrossChainValidator` scans all event payloads for cryptocurrency terminology |
| **6. Report assembly** | All results merged into `IntegrityReport` |
| **7. Alert on DEGRADED** | If any check fails, WF-13 alert triggered with issue details |

---

## Error Handling

| Condition | Status | Action |
|:----------|:-------|:-------|
| Block hash mismatch in Main Chain | `DEGRADED` | Flag tampered block index; alert |
| Proof missing for Sub-Chain | `DEGRADED` | Log missing proof; alert |
| Sub-Chain proof hash ≠ Main Chain proof | `DEGRADED` | Tamper detected; immediate alert |
| Forbidden term found in event | `DEGRADED` | Flag event, log with full path |

---

## Key Classes & Methods

| Step | Class / Method | File |
|:-----|:--------------|:-----|
| Full report | `HierarchyManager.get_system_integrity_report()` | `hierarchical/hierarchy_manager.py` |
| Consistency check | `HierarchyManager.validate_cross_chain_consistency()` | `hierarchical/hierarchy_manager.py` |
| Chain verify | `BlockVerifier.verify_chain()` | `security/verify/block_verifier.py` |
| Per-block verify | `BlockVerifier.verify_block()` | `security/verify/block_verifier.py` |
| Forbidden scan | `CrossChainValidator.validate_system_integrity()` | `domains/generic/utils/cross_chain_validator.py` |
| REST API | `GET /v1/system/integrity` | `api/v1/routes.py` |

---

## See Also

- [WF-2: Proof Anchoring](./wf-02-proof-anchoring.md) — creates the proofs validated here
- [WF-8: Chain Rehydration](./wf-08-chain-rehydration.md) — called if inconsistency triggers rehydration
- [WF-13: Risk Analysis & Alerts](./wf-13-risk-alerts.md) — receives DEGRADED alerts from this workflow
