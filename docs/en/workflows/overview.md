---
title: "Workflows Overview"
description: "Comprehensive guide and developer reference for HieraChain system workflows across core operations, security, consensus, and recovery."
icon: material/routes
---

# Workflows overview and developer guide

HieraChain is a pure Python hierarchical ledger that works as a plugin layer for existing Web2 infrastructure. It does not replace the enterprise network stack, which already handles TLS/SSL, firewalls and WAF at the API gateway. HieraChain is focused on immutability, distributed trust, tamper evidence and non-repudiation.

This document lists workflows in six functional groups. It describes how they interact at runtime and how to read, maintain or add workflows.

## 1. Core development guardrails

When you work on HieraChain workflows, follow these guardrails:

* Strict term censorship: HieraChain tracks business process ledgers, not cryptocurrency. Do not use crypto terms in event payloads, variable names, database keys or comments.

    * Forbidden terms: `transaction`, `mining`, `coin`, `token`, `wallet`, `address`, `sender`, `receiver`, `amount`, `fee`.
    * Required terms: `event` for ledger entries, `node` for peers, `msp_id` for identity, `entity_id` for domain assets.
    * `CrossChainValidator` checks supplied ledger/domain data; it is not a source-code commit hook.

* Minimal latency constraint: The architecture targets low latency; actual latency depends on batching, durability and deployment. Keep workflow code short and fast. Do not add transport level encryption or extra wrappers that add CPU overhead.
* No direct storage access: Do not query SQL or Redis directly. Use storage adapters under `adapters/database/` (for example `adapters/database/sqlite_adapter.py`).

## 2. All workflows: quick reference

This table lists all workflows for quick lookup:

| Workflow | Group | Trigger | Output | Key Module |
|:---------|:------|:--------|:-------|:-----------|
| [Event Submission](./event-submission.md) | A | `POST /api/ledger/chains/{chain_name}/events` | API returns `event_id`; block is created and finalized asynchronously | `hierarchical/sub_chain/base.py` (`SubChain.add_event`) |
| [Proof Anchoring](./proof-anchoring.md) | A | Block finalized on Sub-Chain | Proof hash on Main Chain | `hierarchical/main_chain/base.py` + `hierarchical/sub_chain/proof.py` |
| [Cross-Chain 2PC](./cross-chain-2pc.md) | A | `HierarchyManager.transaction_manager` | `COMMITTED`, `ROLLED_BACK`, or recoverable `IN_DOUBT` | `hierarchical/hierarchy_manager/base.py` + `hierarchical/transaction_manager.py` |
| [BFT Consensus](./bft-consensus.md) | B | BFT component used explicitly; not selected through MainChain/SubChain configuration | Separate BFT consensus workflow | `consensus/bft/consensus.py` |
| [Error Mitigation](./error-recovery.md) | C | Validation error / leader timeout / interrupted event | Classified error, journal replay, or BFT view change | `error_mitigation/error_classifier.py` + `journal.py` + `consensus/bft/view_change.py` |
| [Entity Tracing](./entity-tracing.md) | D | `EntityTracer.trace_entity()` | Complete cross-chain audit trail | `domains/utils/entity_tracer.py` |
| [Chain Rehydration](./chain-rehydration.md) | D | Node restart or hash divergence | In-memory chain synced to DB | `hierarchical/sub_chain/base.py` + `hierarchical/sub_chain/ordering.py` |
| [Integrity Validation](./integrity-validation.md) | D | Explicit application call | Health summary or block/proof consistency report | `hierarchical/hierarchy_manager/validation.py` |
| [Policy Enforcement](./policy-enforcement.md) | E | Explicit `PolicyEngine` call | `allow` or `deny` with decision path | `security/policy_engine.py` |
| [WebSocket Streaming](./websocket-streaming.md) | E | Client connects to `/ws`, optionally passing `chain_name` as a query parameter | Subscriptions; notifications require application broadcast calls | `api/websocket/manager.py` |
| [IPFS Encrypted Storage](./ipfs-storage.md) | E | `IPFSClient.upload_json()` | CID returned; ciphertext on IPFS | `api/storage/ipfs_client.py` |
| [Risk Analysis & Alerts](./risk-alerts.md) | E | Application calls `AlertManager.check_metric()` | Queued notifications and rule-configured escalation | `monitoring/alert_system.py` |
| [ERP Integration Sync](./erp-integration.md) | E | `SyncScheduler` timer | ERP events submitted to Sub-Chain | `integration/erp_ledger.py` |
| [MSP Identity & Auth](./msp-identity.md) | F | Explicit MSP registration/validation calls | Identity confirmed + action authorized | `security/msp.py` |
| [Key Backup & Restoration](./key-backup.md) | F | Operator-managed file/vault backup | Restored identity/provider files | `cli/key.py` + `security/key_provider.py` (no `key_backup_manager.py`) |

## 3. Functional groups and subsystems

Workflows are grouped into six areas. Use the dashboard to find the group that matches the subsystem you are debugging or changing:

<div class="grid cards" markdown>

* :material-sitemap:{ .lg .middle } __Group A: Core chain operations__

    ---

    Handles ingestion, cryptographic validation and persistence.

    * [Event Submission](./event-submission.md)
    * [Proof Anchoring](./proof-anchoring.md)
    * [Cross-Chain Operation (2PC)](./cross-chain-2pc.md)

* :material-shield-key:{ .lg .middle } __Group B: Consensus finalization__

    ---

    Block finalization. For PoA/PoF alternatives, see [Consensus Mechanisms](./consensus_mechanisms.md).

    * [BFT Consensus (3-Phase PBFT)](./bft-consensus.md)

* :material-server-security:{ .lg .middle } __Group C: Cluster management__

    ---

    Governance, lockdown triggers and recovery.

    * [Error Mitigation & Recovery](./error-recovery.md)

* :material-shield-check:{ .lg .middle } __Group D: Integrity and traceability__

    ---

    Auditing, cold start rehydration and integrity verification.

    * [Entity Tracing](./entity-tracing.md)
    * [Chain Rehydration](./chain-rehydration.md)
    * [System Integrity Validation](./integrity-validation.md)

* :material-connection:{ .lg .middle } __Group E: Operational and integration__

    ---

    Policy gates, WebSocket push, encrypted IPFS offloading and ERP sync.

    * [Policy Enforcement](./policy-enforcement.md)
    * [WebSocket Real-Time Streaming](./websocket-streaming.md)
    * [IPFS Encrypted Storage](./ipfs-storage.md)
    * [Risk Analysis & Alert Lifecycle](./risk-alerts.md)
    * [ERP Integration Sync](./erp-integration.md)

* :material-key-chain:{ .lg .middle } __Group F: Identity and key management__

    ---

    Lightweight MSP enrolment (internal `Certificate` in `security/msp.py`), participant authorization and CLI-managed key backup (no X.509/mTLS).

    * [MSP Identity & Authorization](./msp-identity.md)
    * [Key Backup & Restoration](./key-backup.md)

</div>

## 4. How workflows interact

The diagram separates runtime paths from integrations supplied by the application. Dashed lines identify caller-managed connections.

```mermaid
flowchart TD
    CLIENT[Client or SDK] -->|Ledger API| WF1[Event submission]
    ERP[Application ERP sink] -->|add_event| WF1
    WF1 -->|Apply committed block, proof due| WF2[Proof anchoring]
    App -.->|Upload via IPFSClient.upload_json()| WF12[IPFS storage]
    WF12 -.->|Return CID to caller| App
    App -.->|Submit event with details_cid| WF1
    App[Application integration] -.-> MSP[MSP checks]
    App -.-> Policy[PolicyEngine checks]
    App -.-> WS[WebSocket broadcast helpers]
    App -.-> Integrity[Integrity reports]
    Integrity -.->|Caller handles report| Alerts[AlertManager]
    App -.-> Backup[Identity backup]
    App --> Rehydrate[Explicit sync_chain]
    Rehydrate -->|Rebuild chain and indexes| WF1
    Trace[Entity tracing] -->|Read finalized history| WF1
    App --> BFT[Separate BFT library]
    App --> TwoPC[Cross-chain 2PC coordinator]
```

### Core developer integration paths

| Ingestion & Security Chain | Description |
|:---|:---|
| ERP → ERP Sync → Event Submission → Proof Anchoring | Ingestion pipeline: business change → local event → Sub-Chain block → proof hash anchored to root chain. |
| MSP Identity → Policy Enforcement → Event Submission | Caller-managed integration: MSP checks organization roles/policies; a separate `PolicyEngine` check may be added by the application before submission. |
| Integrity Scan → Risk & Alerts → Error Recovery | Caller-managed integration: inspect integrity results, supply an alert metric or rule, then choose an operational recovery action. |
| Error Recovery → Rehydration | Ordering startup replay and Sub-Chain synchronization restore local state; there is no automatic snapshot-failure-to-rehydration hook. |

## 5. Developer guide: how to maintain workflows

Keep workflow documentation in sync with the code when you add features or fix behavior:

### Anatomy of a workflow document
Each workflow page (for example `event-submission.md`) has this layout. It must contain:

1. Zensical front-matter: YAML metadata with `title`, `description` and `icon`. No WF-number prefixes.
2. Clean H1 header: `# [Title]` that matches front-matter.
3. Overview: What the workflow does and when it is used.
4. Flow diagram: Mermaid sequence or flowchart that shows runtime interactions.
5. Step-by-step breakdown: Table that maps sequence numbers to developer actions.
6. Error handling: Table that maps failures (node offline, verification failure) to mitigations.
7. Key classes and methods: Pointers from workflow steps to code (for example `SubChain.add_event()`).
8. Related: Links to sibling or downstream workflows.

### Process for adding or modifying a workflow

1. Write clean Markdown: Save new flows under `docs/en/workflows/name.md` using the design system.
2. Register in zensical.toml: Add the workflow to the `Workflows` tree in [zensical.toml](https://github.com/VanDung-dev/HieraChain/blob/main/zensical.toml) with a clean name.
3. Run term scanner: Check that no forbidden cryptocurrency vocabulary was added.
4. Compile and verify: Run the Zensical build in the HieraChain environment to check formatting and links:

    ```bash
    zensical build -f zensical.toml
    ```
