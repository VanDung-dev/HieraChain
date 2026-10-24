---
title: "Hierarchical Module"
description: "Two-tier architecture: MainChain, SubChain, and HierarchyManager for enterprise scalability and data isolation."
icon: material/layers
---

# Hierarchical Module (`hierachain/hierarchical/*`)

## 1. Overview

The `hierarchical` module implements the two-tier ledger architecture of HieraChain. Sub-Chains process domain business events and store detailed state locally. The Main Chain stores cryptographic proofs and root hashes submitted by Sub-Chains. This separation maintains business data privacy, keeps Main Chain verification lightweight, and scales horizontally by partitioning load across chains.

## 2. Foundational components

Components reside in dedicated packages under `hierachain/hierarchical/`.

### 2.1 Main Chain (`main_chain/base.py`)

* Stores cryptographic block proofs rather than raw business event records.
* Recursively sanitizes Sub-Chain registration metadata before storing it in the registry, consensus authority, or registration event; summaries expose only the sanitized copy.
* Exposes a ZK verification hook; production proving and verification are not implemented.
* Validates cross-chain anchors under consortium or authority consensus.

### 2.2 Sub-Chain (`sub_chain/base.py`)

* Operates dedicated business workflows for a specific domain or department.
* Packages business events into blocks and calculates Merkle roots.
* Generates periodic state proofs for submission to the Main Chain.

Startup loads block headers and ordered events with one SQL range query, while retaining Merkle, hash, trusted-signature, gap, and chain-link checks. Sub-Chain consumes the verified ordering bootstrap snapshot once instead of reading the full chain again; later synchronization reads fresh storage. Recovery rebuilds entity and event-type indexes and counters through the shared Blockchain index helper, so queries reflect the restored ledger.

`validate_cross_chain_consistency()` compares each Sub-Chain tip hash with its latest durably stored MainChain proof. A missing or mismatched proof always sets `overall_consistent` to `false`. When the tip has advanced but the configured proof interval has not elapsed, the per-chain result is `consistent: false, pending: true`; `pending` explains the scheduled wait but does not certify the unanchored tip. A MainChain proof is not treated as an anchor until its signed block has passed durable read-back.

### 2.3 Hierarchy Manager (`hierarchy_manager/base.py`)

* Coordinates chain lifecycles, cross-chain verification, and multi-organization setups.
* Manages communication channels, private data collections, and two-phase commit (2PC) transactions.
* Compiles system-wide integrity reports across all registered chains.

`HierarchyManager` remains the public coordinator and owns resources, shared state, and locks. Internal `recovery.py` replays and verifies durable chain history; `registry.py` handles access snapshots, migration, conditional persistence, refresh, and rollback. `organization.py` builds member/channel views, and `validation.py` produces integrity reports. These helpers share the coordinator's state without creating another registry or storage owner. Existing method signatures, recovery order, cleanup hooks, and storage contracts remain available.

#### Feature support boundary

| Feature | Current behavior |
| :--- | :--- |
| Organization/member/channel registry | SQLite/PostgreSQL persistence and revision checks; explicit memory mode is ephemeral. |
| Organization-to-chain assignment | Persistent SubChain grants for `read`, `write`, and `proofs`; enforced by REST, GraphQL, and WebSocket APIs. Channel membership remains separate. |
| Private collections | Library objects provide an in-memory data store; the manager does not persist collections in its registry. REST private-data writes return HTTP 501. |
| ZK proofs | Mock hashes are development fixtures. Production proving/verification are unimplemented; see [ZK scope](../security/decentralized-zkp.md). |
| ERP vendor connectors | SAP/Oracle/Dynamics fixtures require explicit simulation opt-in. Real transport is application-provided; see [Integration](./integration.md). |
| Contract execution | REST contract registration stores metadata; execution returns HTTP 501. |

`get_cross_chain_statistics()["cross_chain_operations"]` is a reserved field that currently returns `0`, not a measured completed-operation count. A facade method or configuration option alone does not establish end-to-end feature support.

Organization/member/channel access metadata is persisted with an internal `_revision` and `_channel_ledger_version: 1`. Registry snapshots omit channel ledger history. SQLite and PostgreSQL use atomic conditional writes. `RedisLedgerAdapter` supports signed hierarchy blocks and reuses Redis channel-record helpers after checking durable AOF configuration; see [Redis ledger requirements](./storage.md#redis-ledger). Manager provisioning reloads and retries up to three times on an unsuccessful write. REST member provisioning rechecks the authenticated administrator on every retry. Channel configuration conflicts return failure and roll back the local change, requiring fresh endorsement before retry. Reads and channel access checks refresh shared metadata and consume only unseen records for the requested channel while retaining the channel object; unavailable or missing persisted state fails closed. Memory-only managers retain local state.

Legacy registry snapshots containing embedded ledgers are validated and migrated during recovery. Registry replacement and per-channel seed records commit atomically; a failed migration preserves the old snapshot. Upgrade all registry writers together and stop older writers before migration: mixing snapshot writers with append-only writers is unsupported. Custom storage adapters must support `save_hierarchy_registry(state, expected_revision=..., channel_ledgers=...)`, atomically initialize the supplied ledger seeds, and reject stale revisions. They must also implement `append_channel_record(channel_id, record, expected_sequence=..., expected_registry_revision=...)` and `load_channel_records(channel_id, after_sequence=...)`.

Channel submission appends one durable event record before returning success; a storage failure returns HTTP 503 and leaves pending events and counters unchanged. Each append atomically checks both the registry access revision and the channel sequence, so stale workers cannot overwrite history or append using a revoked access snapshot. Finalization appends a signed block record that consumes the current pending batch. SQL adapters store the channel head and records in `channel_ledger_heads` and `channel_ledger_records`; Redis helpers use a per-channel list with WATCH/MULTI checks. Event writes leave registry metadata unchanged and do not serialize earlier blocks or other channels. Finalization writes only the new block batch.

Restart replays channel records, restores pending events, verifies every finalized block against trusted keys and its pending batch, and rebuilds submission counters. Subsequent refreshes apply only the new suffix and update counters incrementally. Invalid suffixes leave local ledger state unchanged. Queries still return finalized blocks; an acceptance ACK does not mean finalization has occurred. Direct channels and explicit memory-only managers remain ephemeral. Full startup verification, ledger memory usage and retained record storage still grow with history; this change adds no retention/compaction. Local access operations retain the manager registry lock.

### 2.4 Multi-organization, channels, and private data

* `multi_org.py`: Manages member organizations, certificates, and MSP identities.
* `channel/manager.py`: Partitions communication between specific groups of organizations.
* `private_data.py`: Provides in-memory encrypted collections and hash helpers; durable storage and automatic ledger anchoring require caller integration.

### 2.5 Organization-to-SubChain access

Organizations and SubChains have a many-to-many relationship. Grants apply to registered organization members whose stored identity matches their user ID, organization, and role. API authentication supplies the user ID; request bodies cannot select a different identity. API key resource permissions remain required alongside the organization grant.

| Grant | API behavior |
| :--- | :--- |
| `read` | Read blocks, events, chain statistics and entity traces; receive WebSocket chain messages. Chain lists and cross-chain traces omit inaccessible SubChains. |
| `write` | Submit events through REST, the secure event endpoint, and GraphQL. API keys still need `events`; the secure endpoint also requires `chains`. |
| `proofs` | Submit a proof through the ledger REST endpoint; the API key still needs `proofs`. |

Read endpoints require `chains`. GraphQL and WebSocket retain their existing transport resource checks; WebSocket streams require both `chains` and `events`. Grants are independent: `write` does not imply `read`, and organization roles do not add grants. Use restricted API key scopes for per-user limits.

Management requires an authenticated key with both `chains` and `chains:manage`. An organization administrator does not automatically receive chain management rights. The existing `all` resource scope includes management, so reserve it for platform administrators.

| Method | Path | Behavior |
| :--- | :--- | :--- |
| GET | `/api/ledger/chains/{chain_name}/organizations` | Return `managed` and the organization-to-permissions mapping. |
| PUT | `/api/ledger/chains/{chain_name}/organizations/{org_id}` | Replace that organization's grants; body: `{"permissions":["read","write"]}`. |
| DELETE | `/api/ledger/chains/{chain_name}/organizations/{org_id}` | Revoke that organization's assignment. |

The SubChain and organization must already exist. PUT requires a nonempty permission list drawn from `read`, `write`, and `proofs`; invalid bodies return HTTP 422. Missing resources/assignments return HTTP 404, and insufficient management rights return HTTP 403. Create organizations and register their members through the existing business API before assigning them.

```python
manager.assign_organization_to_chain("logistics", "supply_chain", permissions=["read", "write"])
manager.can_access_chain("supply_chain", "alice", "read")
manager.get_chain_access("supply_chain")
manager.revoke_organization_from_chain("logistics", "supply_chain")
```

The Python assignment method defaults to `read` and `write` when permissions are omitted, returns `False` for a missing organization/SubChain, and raises `ValueError` for invalid permissions. It replaces that organization's existing list. `get_chain_access()` returns `None` for an unmanaged chain and a copied mapping for a managed chain.

Compatibility and deployment: chains without assignments retain legacy API access under existing resource scopes. The first assignment enables organization checks for all historical and future API reads of that SubChain. Revoking the final assignment leaves a managed empty mapping, denying member access until a new grant is added. There is no API operation to restore unmanaged access. Deploy the upgraded version to every API worker and registry writer before enabling assignments; mixed versions are unsupported. Disabled authentication cannot access managed chains.

Grants are stored in `chain_access` inside the existing hierarchy registry with revision retries and rollback; legacy snapshots without that field load as unmanaged. Shared SQLite/PostgreSQL/Redis managers refresh the registry on access checks and fail closed if persisted state is unavailable. Memory-only managers remain ephemeral. WebSocket subscriptions check access when subscribing and before each chain broadcast, including wildcard and event-type subscriptions; revocation prevents later authorized sends but cannot retract data already sent or queued. A request already past its authorization check may finish; SubChain event writes do not atomically compare the registry revision at append time.

This is API authorization, not a separate encrypted ledger per organization. MainChain proofs, registration metadata and aggregate node counters remain shared. Trusted in-process calls to chain objects are privileged; embedding applications must call `can_access_chain()` before exposing them to users. Channel policies and channel ledgers remain independent, with no automatic SubChain assignment or anchoring.

#### Docker verification

```bash
.venv/bin/python docker/scripts/verify_chain_access.py --context orbstack
```

Omit `--context orbstack` to use the current Docker context. The runner builds a production wheel and both Docker image stages from a disposable copy of the current checkout, including local changes. It generates temporary identities and API keys, starts three authenticated production API containers with SQLite/PostgreSQL/Redis, and calls their real HTTP/WebSocket endpoints from a separate test container. No API dependencies are replaced in the live tests.

Checks cover management scopes, selected organization permissions, REST/GraphQL writes and reads, signed secure events, proof submission, entity traces, WebSocket admission/subscription revocation, and two application-container recreations with retained volumes. They also run the Docker runtime suite and 20 regression files individually inside Linux containers, including shared-registry backend tests with skips treated as failures. Broadcast filtering is exercised by the regression tests; the live suite does not introduce an automatic ledger-to-WebSocket publisher. This is scoped organization–chain verification, not a P2P consensus or stress/soak test.

Logs and JUnit XML remain in the printed temporary reports directory. The runner removes its own containers, networks, volumes and generated credentials even on failure. Existing deployments and repository data directories are not mounted into the test stack. See `docker/docker-compose.chain-access.yml` for the isolated services.

## 3. Data flow

Detailed data remains on Sub-Chains. Merkle roots and signed block proofs anchor to the Main Chain. The optional ZK branch in this design flow has only a mock implementation:

```mermaid
graph TD
    subgraph "Sub-Chain (Logistics/Finance/...)"
        A[Business Events] --> B[Ordering Service]
        B --> C[Block Builder]
        C --> D[(Local DB)]
        C --> E[Merkle Tree / ZK Prover]
    end

    subgraph "Main Chain (Root Authority)"
        F[ZK Verifier] --> G[Proof Storage]
        G --> H[(Global Integrity State)]
    end

    E -- "Submit Proof (Hash + ZKP)" --> F

    subgraph "Hierarchy Manager"
        I[Transaction Manager 2PC]
    end

    I -. "Coordinate" .-> A
```

## 4. Cross-chain operations (2PC)

The coordinator acquires its journal writer on first use. Registry/channel-only managers can share a SQL registry without acquiring a 2PC writer when no coordinator history exists. Existing `data/transactions` history is recovered at startup and retains the exclusive journal lease. Shared 2PC or SubChain journal paths still require one owning writer; registry concurrency does not provide multiple ordering/coordinator writers.

Call `HierarchyManager.close()` when its owner finishes. It closes sub-chain orderers, an acquired coordinator, and storage without creating an unused journal. `SubChain.stop()` drains committed blocks and releases its orderer and writer lease, allowing a replacement instance to recover the same paths. Entity consistency validation tracks operation and status state separately for each chain.

`CrossChainTransactionManager` in `hierachain/hierarchical/transaction_manager.py` implements a two-phase commit protocol to maintain atomicity across Sub-Chains:

Coordinator phase ACKs and participant commit ACKs still require durable journal read-back. Native journals use `read_since(cursor)` to decode new records after an initial history scan, including records in rotated files. Participant retries retain durable event IDs to avoid duplicate appends; ambiguous submissions invalidate their marker snapshot. Custom journals exposing only `replay()` keep the full replay path. Transaction history and archive count remain unbounded; this change does not add retention or compaction.

```python
from hierachain.hierarchical.hierarchy_manager import HierarchyManager

manager = HierarchyManager()
tx_id = manager.initiate_cross_chain_transaction(
    source_chain_name="supply_chain",
    dest_chain_name="finance_chain",
    payload={"asset_id": "INV-100", "action": "settle_payment"}
)
```

## 5. Privacy and zero-knowledge verification

* Main Chain verification: Signed block proofs and Merkle anchors provide the implemented integrity path. Mock ZK proofs do not establish state-transition correctness or zero-knowledge privacy; production ZK is unavailable.
* Private data collections: The library offers encrypted in-memory payloads and organization checks. Applications must integrate durable storage and hash anchoring; REST writes remain unimplemented.

## Related

* [Consensus Module](./consensus.md)
* [Domains Module](./domains.md)
* [Two-Phase Commit Guide](../how-to/cross-chain-transactions.md)

## Entity projection and proof roots

A Sub-Chain initializes `WorldState` from its local genesis before startup synchronization. Rehydration clears the projection and applies the persisted history once; repeated synchronization with an unchanged tip does not increment entity event counts.

`WorldState.get_state_root()` hashes the current entity projection for diagnostics. Cross-level proof metadata and ZK public inputs use block event Merkle roots: the previous block root and the latest block root (or the existing genesis/hash fallback where applicable). Anchoring therefore commits the block event history contract, not the entity projection root. Changing that commitment would require a separate proof schema and verifier migration.
