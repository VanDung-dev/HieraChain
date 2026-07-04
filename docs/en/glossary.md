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
| Consensus | Block approval mechanism (PoA, PoF, BFT); `hierachain/consensus/*`, `hierachain/hierarchical/consensus/*`. |
| Membership Service Provider | MSP; identity/organization management; `hierachain/security/msp.py`, `hierachain/security/identity.py`. |
| Policy | Access/resource control; `hierachain/security/policy_engine.py`, `hierachain/security/resource_guard.py`. |
| World State | Current data state; `hierachain/state/world_state.py`. |
| Journal | Transaction log; `hierachain/error_mitigation/journal.py`. |
| Rollback | State restoration; `hierachain/error_mitigation/rollback_manager.py`. |
| Recovery | Error recovery mechanism; `hierachain/error_mitigation/recovery_engine.py`. |
| Ordering | Event ordering; `hierachain/consensus/ordering/*`. |
| Transport | Network communication; `hierachain/network/zmq_transport.py`. |
| Byzantine Fault Tolerance | BFT; `hierachain/consensus/bft/*`. |
| Proof of Authority | PoA; static validator consensus; `hierachain/consensus/proof_of_authority.py`. |
| Proof of Federation | PoF; federation consensus; `hierachain/consensus/proof_of_federation.py`. |
| API Key | API access key; `hierachain/security/verify/api_key_verifier.py`. |
| Resource Guard | Resource protection middleware; `hierachain/security/resource_guard.py`. |
| Entity Tracer | Event tracing by entity; `hierachain/domains/generic/utils/entity_tracer.py`. |
| Zero-Knowledge Proof | ZK Proof; `hierachain/security/zk_prover.py`, `hierachain/security/verify/zk_verifier.py`. |
| Proof Aggregation | Multiple proof aggregation; `hierachain/hierarchical/proof_aggregation.py`. |
| Rebalancer | Automatic Sub-Chain splitting/balancing; `hierachain/hierarchical/rebalancer.py`. |
| Channel | Inter-organization private channel; `hierachain/hierarchical/channel.py`. |
| Multi-Organization | Multi-org network; `hierachain/hierarchical/multi_org.py`. |
| Private Data | Private data collections; `hierachain/hierarchical/private_data.py`. |
| Performance Monitor | Performance monitoring; `hierachain/monitoring/performance_monitor.py`. |
| Rate Limiting | Request rate limiting; configured in `hierachain/config/settings.py`. |
| HTTP Strict Transport Security | HSTS; `hierachain/config/settings.py`. |
| Cross-Origin Resource Sharing | CORS; `hierachain/config/settings.py`. |
| Command Line Interface | CLI `hrc` tool; `hierachain/cli/*`. |
| API Ledger | REST API Ledger; `hierachain/api/ledger/*`. |
| API business | REST API business; `hierachain/api/business/*`. |
| API Admin | REST API Admin; `hierachain/api/admin/*`. |
| Cross-level State Sync | Cross-tier state synchronization; `hierachain/cluster/state_sync_manager.py`. |
| Kubernetes Namespace | Sub-Chain namespace isolation; `hierachain/hierarchical/k8s_namespace_manager.py`. |
| Identity Manager | Organization/user/role management; `hierachain/security/identity.py`. |
| Certificate | X.509 certificate management; `hierachain/security/certificate.py`. |
