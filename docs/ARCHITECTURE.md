# HieraChain Architecture

*Last updated: 2026-01-12*

## 📋 Overview

HieraChain is a **pure Python, high-performance enterprise blockchain ledger**. The architecture follows a **layered approach**, heavily utilizing **Apache Arrow** for fast columnar data processings and focusing on true enterprise integration rather than cryptocurrency mining natively.

---

## 📑 Table of Contents

* [🏗️ High-Level Architecture](#️-high-level-architecture)
* [📦 Project Structure](#-project-structure)
* [🏛️ Hierarchical Chain Architecture](#️-hierarchical-chain-architecture)
* [🔄 Data Flow Architecture](#-data-flow-architecture)
* [⚙️ Consensus Mechanism & Ordering](#️-consensus-mechanism--ordering)
* [🛡️ Zero Knowledge Proof (ZKP) Verification Layer](#️-zero-knowledge-proof-zkp-verification-layer)
* [⚖️ Cluster & Risk Management](#-cluster--risk-management)
* [🔐 Security Architecture](#-security-architecture)
* [📊 Performance Architecture](#-performance-architecture)
* [🌐 Network Architecture](#-network-architecture)
* [📈 Monitoring & Observability](#-monitoring--observability)
* [📄 License](#-license)

---

## 🏗️ High-Level Architecture

### System Overview

```mermaid
flowchart TB
    CLIENT["🖥️ <b>Client Applications</b><br/>Web Apps · Mobile · CLI · External Services"]
    
    API["🌐 <b>API Gateway Layer</b><br/>FastAPI · WebSocket · GraphQL"]
    
    CORE["⚙️ <b>Core Components</b><br/>Consensus · Hierarchical Chains · Security"]
    
    CLUSTER["⚖️ <b>Cluster & Management</b><br/>Lockdown Protocol · Risk Analyzer"]
    
    STORAGE["💾 <b>Data & Storage Layer</b><br/>SQLite/Redis · IPFS · World State · Arrow IPC"]

    CLIENT --> API --> CORE
    CORE <--> CLUSTER
    CORE --> STORAGE
```

### Core Components Detail

```mermaid
flowchart LR
    subgraph HieraChain_Core["⚙️ HieraChain Core"]
        direction TB
        subgraph Hierarchical["Hierarchical System"]
            H1["Main Chain"]
            H2["Sub Chains"]
            H3["Channels"]
        end
        
        subgraph Consensus["Consensus & Security"]
            C1["Ordering Service"]
            C2["PoA / PoF / BFT"]
            C3["Policy Engine (ABAC)"]
            C4["ZK Verifier"]
        end
        
        Hierarchical <--> Consensus
    end
```

### Storage Layer Detail

```mermaid
flowchart LR
    S1[("SQL / Redis Backend")]
    S2[("In-Memory Cache")]
    S3[("World State")]
    S4[("Arrow IPC Files")]

    S1 --- S2 --- S3 --- S4
```

---

## 📦 Project Structure

```
HieraChain Ecosystem/
├── hierachain/                    # 🐍 Python - Main Ledger
│   ├── adapters/                  # Storage/DB adapters (SQLite, Redis)
│   ├── api/                       # REST, GraphQL, WebSocket, Explorer
│   ├── cli/                       # Command-line interface
│   ├── cluster/                   # ⚖️ Cluster Quorum & Sync
│   ├── config/                    # Configuration management
│   ├── consensus/                 # ⚙️ Ordering Service, BFT, PoA, PoF
│   ├── core/                      # Core blockchain components
│   ├── domains/                   # 🏢 Business domain logic & Event Types
│   ├── error_mitigation/          # Error handling & recovery
│   ├── hierarchical/              # Hierarchical chain system
│   ├── integration/               # Enterprise logic (ERP connectors)
│   ├── monitoring/                # 📈 Observability & Alerts
│   ├── network/                   # P2P Network (ZMQ)
│   ├── risk_management/           # 🛡️ Risk assessment & Mitigation
│   ├── security/                  # Cryptography, PoA, ACL
│   ├── storage/                   # Data persistence abstractions
│   └── units/                     # Semantic versioning & Utils
│
├── tests/                         # Unit, Integration, Stress tests
├── docs/                          # Developer documentation
├── pyproject.toml                 # Python dependencies
└── requirements.txt               # Main dependencies
```

---

## 🏛️ Hierarchical Chain Architecture

```mermaid
flowchart BT
    %% Main Chain
    MC["🔗 <b>MAIN CHAIN</b><br/>━━━━━━━━━━━━━━━━<br/>Global State & Anchoring<br/>• Global consensus<br/>• Cross-chain transactions<br/>• Anchor blocks from sub-chains"]

    %% Sub Chains
    SCA["📦 <b>SUB-CHAIN A</b><br/>Organization 1<br/>─────────────<br/>• Local consensus<br/>• Private data<br/>• Domain contracts"]
    SCB["📦 <b>SUB-CHAIN B</b><br/>Organization 2<br/>─────────────<br/>• Local consensus<br/>• Private data<br/>• Domain contracts"]
    SCC["📦 <b>SUB-CHAIN C</b><br/>Organization 3<br/>─────────────<br/>• Local consensus<br/>• Private data<br/>• Domain contracts"]

    %% Channels
    CHA["💬 Channel A<br/>(Private Comms)"]
    CHB["💬 Channel B<br/>(Private Comms)"]
    CHC["💬 Channel C<br/>(Private Comms)"]

    %% Data Flow / Proof Anchoring connections
    SCA --> MC
    SCB --> MC
    SCC --> MC
    
    %% Channel Private connections
    CHA --> SCA
    CHB --> SCB
    CHC --> SCC
```

---

## 🔄 Data Flow Architecture

### Transaction Processing Flow

```mermaid
flowchart TB
    CR["📨 <b>Client Request</b><br/>REST / Arrow IPC / WebSocket"]
    
    EP["🚪 <b>Entry Points</b><br/>Python FastAPI · Arrow IPC · WebSocket"]
    
    MP["📋 <b>Mempool</b><br/>Transaction Batching"]
    
    WP["⚡ <b>Worker Pool</b><br/>Parallel Processing"]
    
    EX["🔄 <b>Parallel Execution</b><br/>Pure Python Consensus + Python Business Logic"]
    
    BF["✅ <b>Block Finalization</b><br/>Python Core"]
    
    OUT["📤 <b>Output</b><br/>Network P2P · Storage · Monitoring"]

    CR --> EP --> MP --> WP --> EX --> BF --> OUT
```

---

## ⚖️ Cluster & Risk Management

### Cluster Quorum Protocol

HieraChain implements a robust, Quorum-based cluster protocol (instead of single-leader election) to manage distributed states safely:

* **Heartbeat & Health Sync**: Continuous peer validation across the cluster.
* **Lockdown Protocol**: If severe anomalies occur, nodes cast votes. A quorum triggers a system-wide lockdown to freeze state changes.
* **Recovery Voting**: Upon resolution, the cluster votes to lift the lockdown.

### Risk Analyzer

Runs concurrently alongside operations to detect anomalies such as:

* Abnormal transaction volume (Z-score analysis).
* Suspicious cross-chain activity.
* Entity misbehaviors.

---

## ⚙️ Consensus Mechanism & Ordering

### Supported Algorithms

| Algorithm | Language | Use Case |
|:----------|:---------|:---------|
| **Proof of Authority (PoA)** | Python | Private networks with trusted validators |
| **Proof of Federation (PoF)** | Python | Multi-organization permissioned networks |
| **BFT Consensus** | Python | Byzantine fault-tolerant ordering |
| **Ordering Service** | Python | Transaction ordering & batching |

### Algorithm Summary

| Algorithm | Key Concept | Fault Tolerance |
|:----------|:------------|:----------------|
| **PoA** | Identity-based validation by trusted authorities | Relies on validator reputation |
| **PoF** | Quorum-based consensus across organizations | Distributed trust, no single control |
| **BFT** | Tolerates Byzantine faults (malicious nodes) | Up to `f` faulty nodes in `3f + 1` network |

---

## 🛡️ Zero Knowledge Proof (ZKP) Verification Layer

### Overview

The ZKP layer enhances HieraChain's consensus mechanisms (PoA/PoF) from **Trust-Based** to a **Trustless** verification model:

| Model | Consensus | Trust Basis | Verification | Security Level |
|:------|:----------|:------------|:-------------|:---------------|
| **PoA/PoF (Base)** | Authority/Federation | Identity & Reputation | Signature only | Medium |
| **PoA/PoF + ZKP** | Authority/Federation | Cryptographic Proof | Mathematical verification | High |

> **Note**: Both **Proof of Authority (PoA)** and **Proof of Federation (PoF)** inherit from `BaseConsensus`, which provides the shared ZKP verification logic via `_verify_block_zk_proof()`.

### Architecture

```mermaid
flowchart BT
    subgraph SubChain["📦 SubChain"]
          direction LR
          ZKP["ZKProver"]
          GP["generate_proof()"]
          PB["[proof bytes]"]
          ZKP --> GP --> PB
    end

    subgraph MainChain["🔗 MainChain"]
          direction LR
          ZKV["ZKVerifier"]
          VP["verify_proof()"]
          RES["[true/false]"]
          ZKV --> VP --> RES
    end

    SubChain -->|"🔐 ZK Proof + Metadata"| MainChain
```

### ZK Components

| Component | Location | Responsibility |
|:----------|:---------|:---------------|
| `ZKProver` | `hierachain/security/zk_prover.py` | Generate proofs for block state transitions |
| `ZKVerifier` | `hierachain/security/zk_verifier.py` | Verify ZK proofs from SubChains |
| `BaseConsensus._verify_block_zk_proof()` | `hierachain/consensus/base_consensus.py` | Shared ZK verification logic |

### ZK State Transition Model

```mermaid
flowchart LR
    SR["State Root<br/>(Previous)"]
    TX["Transactions<br/>(Witness)"]
    NSR["New State<br/>Root"]

    PI["PUBLIC INPUT"]
    PRI["PRIVATE INPUT"]
    PO["PUBLIC OUTPUT"]

    SR --> TX --> NSR
    SR -.-> PI
    TX -.-> PRI
    NSR -.-> PO
```

### Public Inputs (Verifiable)

| Field | Type | Purpose |
|:------|:-----|:--------|
| `old_state_root` | `bytes` | Merkle root of previous block |
| `new_state_root` | `bytes` | Merkle root of new block |
| `block_index` | `int` | Sequential block number (prevents replay) |

### Consensus Integration

ZK verification is integrated into all consensus mechanisms:

* **ProofOfAuthority (PoA)**: Uses `_verify_block_zk_proof()` from `BaseConsensus`
* **ProofOfFederation (PoF)**: Uses `_verify_block_zk_proof()` from `BaseConsensus`
* **BFTConsensus**: Includes `_verify_operation_zk_proof()` in `_handle_pre_prepare`
* **OrderingService**: `EventCertifier.validate()` includes `_verify_zk_proof()` method

### Configuration

| Setting | Default | Description |
|:--------|:--------|:------------|
| `ENABLE_ZK_PROOFS` | `False` | Enable/disable ZK verification |
| `ZK_MODE` | `"mock"` | `"mock"` for development, `"production"` for real ZK |
| `ZK_VERIFICATION_KEY_PATH` | `""` | Path to ZoKrates verification key |
| `ZK_PROVING_KEY_PATH` | `""` | Path to ZoKrates proving key |

### Modes

* **Mock Mode**: Uses SHA-256 hashes to simulate ZK proofs (development)
* **Production Mode**: Uses **ZoKrates** for real ZK-SNARKs circuits

### Security Guarantees

* ✅ **Soundness**: Cannot forge a valid proof for an invalid state transition
* ✅ **Completeness**: Valid state transitions always produce valid proofs
* ✅ **Zero-Knowledge**: Proof reveals nothing about private transaction data
* ✅ **Non-Interactive**: No communication needed between prover and verifier
* ✅ **Succinct**: Proof size is constant regardless of transaction count

---

## 🛡️ Enterprise Security Architecture

HieraChain adopts an omnipresent security philosophy relying on **6 core pillars**. Rather than being a single module, these pillars bind components across `hierachain.security`, `hierachain.cluster`, and `hierachain.risk_management` into a holistic enterprise-grade defense mechanism:

* 👤 **Authorization**: `PolicyEngine` (ABAC) and MSP Identity enforcing zero-trust access control.
* 🔒 **Lockdown & Logging**: `ClusterLockdownManager` via Quorum voting, paired with tamper-evident `SecureLogger`.
* 🛡️ **Fault-tolerance**: BFT and PoF consortium models resisting Byzantine behaviors and network splits.
* 📈 **Risk Analyzer**: Real-time Z-score anomaly detection to identify and flag suspicious transaction patterns.
* 🔑 **Encryption**: AES-256-GCM for all IPFS Swarm data, Ed25519 signatures, and mTLS/ZMQ Curve for the transport layer.
* 🔐 **Decentralized Zero-Knowledge Proofs**: ZK circuits (`ZKProver`/`ZKVerifier`) allowing systemic truth verification without revealing raw private data on the Main Chain.

```mermaid
flowchart TB
    subgraph ALFRED["Comprehensive Security Framework"]
        direction TB
        A["👤 <b>Authorization</b><br/>PolicyEngine / MSP"]
        L["🔒 <b>Lockdown</b><br/>Quorum / SecureLog"]
        F["🛡️ <b>Fault-tolerance</b><br/>BFT / PoF"]
        R["📈 <b>Risk Analyzer</b><br/>Z-score Monitor"]
        E["🔑 <b>Encryption</b><br/>AES-256-GCM / Ed25519"]
        D["🔐 <b>Decentralized Proofs</b><br/>ZK Verifier"]
        
        A ~~~ L ~~~ F
        R ~~~ E ~~~ D
    end
```

---

## 📊 Performance Architecture

Despite being written natively in Python, HieraChain achieves high throughput via advanced data processing paradigms:

```mermaid
flowchart TB
    subgraph Performance["Performance Optimization Strategies"]
        L1["🔄 <b>Columnar Storage</b><br/>Apache Arrow<br/>───────────<br/>High-speed bulk <br/>data processing"]
        L2["🔀 <b>Parallel Processing</b><br/>Worker Pool<br/>───────────<br/>Concurrent execution<br/>Configurable workers"]
        L3["🔗 <b>High-Speed Transport</b><br/>Arrow Flight<br/>───────────<br/>Enterprise ERP <br/>data streaming"]
        L1 ~~~ L2 ~~~ L3
    end

    subgraph Batching["Batching & Caching"]
        L4["📦 <b>Batch Operations</b><br/>Events<br/>───────────<br/>batch_create_blocks<br/>batch_calculate_hashes"]
        L5["📋 <b>TX Batching</b><br/>Ordering<br/>───────────<br/>Groups transactions<br/>Efficient processing"]
        L6["💾 <b>Cache Layer</b><br/>World State<br/>───────────<br/>In-memory caching<br/>Redis indexing"]
        L4 ~~~ L5 ~~~ L6
    end

    Performance --> Batching
```

---

## 🌐 Network Architecture

```mermaid
flowchart LR
    subgraph Bootstrap["Bootstrap/Seed Nodes"]
        BS["Seed Nodes"]
    end

    subgraph Peers["Peer Nodes"]
        subgraph Peer1["Peer Node 1"]
            P1E["ZmqNode Engine"]
            P1A["Python Core"]
            P1E ~~~ P1A
        end
        subgraph Peer2["Peer Node 2"]
            P2E["ZmqNode Engine"]
            P2A["Python Core"]
            P2E ~~~ P2A
        end
        subgraph Peer3["Peer Node 3"]
            P3E["ZmqNode Engine"]
            P3A["Python Core"]
            P3E ~~~ P3A
        end
    end

    subgraph Protocols["Message Protocols"]
        MP1["ZeroMQ (Fast)"]
        MP2["HTTP/REST (Structured)"]
        MP3["WebSocket (Streaming)"]
        MP1 ~~~ MP2 ~~~ MP3
    end

    Bootstrap --> Peers
    Peers --> Protocols
    Peer1 <--> Peer2 <--> Peer3
    Peer1 <--> Peer3
```

---

## 📈 Monitoring & Observability

```mermaid
flowchart TB
    subgraph ObsStack["Observability Stack"]
        direction TB
        subgraph Tools["Monitoring Tools"]
            direction LR
            PROM["Prometheus (Metrics)<br/>tx_count<br/>block_time<br/>queue_size"]
            GRAF["Grafana (Dashboards)<br/>Performance<br/>Health<br/>Alerts"]
            LOG["Logging (Structured)<br/>JSON logs<br/>Trace IDs<br/>Rotation"]
        end

        ENGINE["API Service (metrics)<br/>Port: 2112 (/metrics)"]

        ENGINE --> PROM --> GRAF
    end
```

---

## 📄 License

Dual licensed under [Apache-2.0](LICENSE-APACHE) or [MIT](LICENSE-MIT).

---
