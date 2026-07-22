---
title: "Codebase Map"
description: "Concept-to-Source-Code mapping to help AI and Developers quickly locate source files."
icon: material/map
---

# Codebase Map

This document maps concepts in technical documentation to specific source code files. It helps AI and Developers quickly locate code based on context.

## Core Architecture

| Concept | File Path | Role |
|---------|-----------|------|
| **Blockchain (Base)** | `hierachain/core/blockchain.py` | Base class managing chain, adding blocks, integrity checks. |
| **Block Structure** | `hierachain/core/block.py` | Defines Block structure (Index, Hash, Data, Proof). |
| **Main Chain** | `hierachain/hierarchical/main_chain/base.py` | Main chain (Layer 1), stores Proof only and manages Sub-chains. |
| **Sub Chain** | `hierachain/hierarchical/sub_chain/base.py` | Sub chain (Layer 2), processes Domain data and creates Proof. |
| **Hierarchy Manager** | `hierachain/hierarchical/hierarchy_manager/base.py` | Coordinator managing Main/Sub-chain lifecycle. |

## Consensus & Ordering

| Concept | File Path | Role |
|---------|-----------|------|
| **Ordering Service** | `hierachain/consensus/ordering/service.py` | Receives Events, orders them before Block creation. |
| **Block Builder** | `hierachain/consensus/ordering/block_builder.py` | Builds blocks from ordered transactions. |
| **Block Manager** | `hierachain/consensus/ordering/block_manager.py` | Manages block lifecycle in the ordering system. |
| **Proof of Authority** | `hierachain/consensus/proof_of_authority.py` | PoA consensus mechanism (Intra-Organization). |
| **Proof of Federation** | `hierachain/consensus/proof_of_federation.py` | PoF consensus mechanism (Inter-Organization Consortium). |
| **BFT Consensus** | `hierachain/consensus/bft/consensus.py` | Byzantine Fault Tolerant consensus (for Production). |

## API & Interfaces

| Concept | File Path | Role |
|---------|-----------|------|
| **API Server** | `hierachain/api/server.py` | FastAPI server entry point. |
| **API Ledger** | `hierachain/api/ledger/router.py` | Basic API (Blocks, Chain info). |
| **API Business** | `hierachain/api/business/router.py` | Advanced API (Events, Domain). |
| **API Admin** | `hierachain/api/admin/` | System API (Admin, Health). |
| **WebSocket Manager** | `hierachain/api/websocket/manager.py` | Manages real-time WebSocket connections. |
| **GraphQL Schema** | `hierachain/api/graphql/schema.py` | GraphQL schema for flexible queries. |
| **IPFS Client** | `hierachain/api/storage/ipfs_client.py` | Off-chain storage integration (AES-256-GCM). |
| **Blockchain Explorer** | `hierachain/api/blockchain_explorer.py` | Chain analysis and visualization interface. |
| **CLI Entry** | `hierachain/__main__.py` | Entry point for `python -m hierachain`. |
| **SDK Client** | `hierachain/sdk/client.py` | Python library for external applications to interact with Chain. |

## Security & Identity

| Concept | File Path | Role |
|---------|-----------|------|
| **MSP (Membership)** | `hierachain/security/msp.py` | Manages Identity and membership certificates. |
| **ZK Prover** | `hierachain/security/zk_prover.py` | Creates Zero-Knowledge proofs (data privacy). |
| **Policy Engine** | `hierachain/security/policy_engine.py` | Enforces access control rules. |
| **Key Manager** | `hierachain/security/key_manager.py` | Manages Cryptographic keys. |
| **Key Provider** | `hierachain/security/key_provider.py` | Provides keys to Node. |
| **Block Verifier** | `hierachain/security/verify/block_verifier.py` | Validates Block integrity. |
| **Signature Verifier** | `hierachain/security/verify/signature_verifier.py` | Validates digital signatures. |

## Storage & Persistence

| Concept | File Path | Role |
|---------|-----------|------|
| **SQLite Adapter** | `hierachain/adapters/database/sqlite_adapter.py` | Light weight, high performance SQLite database storage. |
| **Redis Adapter** | `hierachain/adapters/database/redis_adapter.py` | Key-value store for caching and consensus state. |

## Network & Cluster

| Concept | File Path | Role |
|---------|-----------|------|
| **Network Client** | `hierachain/network/network_client.py` | Communication & Data exchange between Nodes. |
| **ZMQ Transport** | `hierachain/network/zmq_transport.py` | Messaging protocol over ZeroMQ. |
| **Message Crypto** | `hierachain/network/message_cryptographic.py` | Message encryption between Nodes. |
| **Peer Trust Manager** | `hierachain/network/peer_trust_manager.py` | Manages Peer-to-Peer trust. |
| **Secure Connection** | `hierachain/network/secure_connection.py` | Establishes secure connections between nodes. |
| **Cluster Manager** | `hierachain/cluster/cluster_manager.py` | Manages state and membership in cluster. |
| **State Sync** | `hierachain/cluster/state_sync_manager.py` | State synchronization between cluster nodes. |
| **Lockdown Protocol** | `hierachain/cluster/lockdown_protocol.py` | Cluster lockdown protocol when critical issues are detected. |
| **Cross-Chain Sync** | `hierachain/cluster/cross_level_sync.py` | Cross-level data synchronization (Main <-> Sub). |

## Monitoring & Risk Management

| Concept | File Path | Role |
|---------|-----------|------|
| **Alert System** | `hierachain/monitoring/alert_system.py` | Real-time alert system. |
| **Performance Monitor**| `hierachain/monitoring/performance_monitor.py` | System performance monitoring (CPU, RAM, TPS). |
| **Risk Analyzer** | `hierachain/risk_management/risk_analyzer.py` | Risk analysis based on system behavior. |
| **Audit Logger** | `hierachain/risk_management/audit_logger.py` | Audit logging for traceability. |

## CLI & Configuration

| Concept | File Path | Role |
|---------|-----------|------|
| **CLI Commands** | `hierachain/cli/` | Admin commands: `chain`, `node`, `event`, `verify`. |
| **Configuration** | `hierachain/config/settings.py` | Manages environment variables and system configuration. |
| **Logging Config** | `hierachain/config/logging.py` | Centralized logging system configuration. |

## Advanced Modules

| Concept | File Path | Role |
|---------|-----------|------|
| **Error Mitigation** | `hierachain/error_mitigation/` | Self-recovery mechanisms (Rollback, Journal). |
| **Integration (ERP)** | `hierachain/integration/enterprise.py` | Connection to external enterprise systems. |
| **Domains** | `hierachain/domains/` | Domain-specific business logic (chains, events, utils). |
| **Units** | `hierachain/units/` | Version management and semantic versioning. |
