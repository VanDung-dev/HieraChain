---
title: Glossary
description: Glossary of terms used in the documentation, maintaining Vietnamese ↔ English consistency.
icon: material/alphabetical
---

# Glossary

| Term | Description |
|---|---|
| Chain | Logical block chain; HieraChain has Main Chain and Sub-Chain. |
| Block | Data unit containing Events; defined in `hierachain/core/block.py`. |
| Blockchain | Block chain management; `hierachain/core/blockchain.py`. |
| Consensus | Block approval mechanism (PoA, PoF); `hierachain/consensus/*`, `hierachain/hierarchical/consensus/*`. |
| HieraChain | Hierarchical blockchain ledger for business use cases. |
| Node ID | Identifier of a HieraChain node (`NODE_ID`/`HRC_NODE_ID`). |
| World State | Current data state; `hierachain/state/world_state.py`. |
| Journal | Transaction log; `hierachain/error_mitigation/journal.py`. |
| Rollback | Transaction rollback owned by `hierachain/hierarchical/transaction_manager.py`; no global state rollback manager is provided. |
| Recovery | Runtime recovery through journal replay, validation, and deployment procedures. |
| Ordering | Event ordering; `hierachain/consensus/ordering/*`. |
| Transport | Network communication; `hierachain/network/zmq_transport.py`. |
| Proof of Authority | PoA; Intra-Organization consensus; `hierachain/consensus/proof_of_authority.py`. |
| Proof of Federation | PoF; Inter-Organization P2P MainChain Alliance consensus; `hierachain/consensus/proof_of_federation.py`. |
| API Key | API access key; `hierachain/security/verify/api_key_verifier.py`. |
| API-key brute-force protection | Tracks failed API-key authentication attempts by IP and applies temporary IP lockouts; the key prefix is used only for logging; `hierachain/security/brute_force_protector.py`. |
| Entity Tracer | Event tracing by entity; `hierachain/domains/utils/entity_tracer.py`. |
| Zero-Knowledge Proof | ZK Proof; `hierachain/security/zk_prover.py`, `hierachain/security/verify/zk_verifier.py`. |
| Channel | Inter-organization private channel; `hierachain/hierarchical/channel/channel.py`. |
| Multi-Organization | Multi-org network; `hierachain/hierarchical/multi_org.py`. |
| Private Data | Private data collections; `hierachain/hierarchical/private_data.py`. |
| Ledger | Append-only chain of blocks storing business events. |
| Rate Limiting | Request rate limiting; configured in `hierachain/config/settings.py`. |
| HTTP Strict Transport Security | HSTS; `hierachain/config/settings.py`. |
| Cross-Origin Resource Sharing | CORS; `hierachain/config/settings.py`. |
| Command Line Interface | CLI `hrc` tool; `hierachain/cli/*`. |
| API Ledger | REST API Ledger; `hierachain/api/ledger/*`. |
| API business | REST API business; `hierachain/api/business/*`. |
| API Admin | REST API Admin; `hierachain/api/admin/*`. |
| Cross-level State Sync | Cross-tier sync via `hierachain/cluster/cross_level_sync.py` + `hierachain/hierarchical/hierarchy_manager/` + `HRC_CROSS_LEVEL_*` settings. |
| World State | In-memory projection of the latest entity state derived from verified blocks. |
| Node identity | Runtime identity loaded from `HRC_VALIDATOR_IDENTITY`; see `hierachain/security/identity_loader.py`. |
