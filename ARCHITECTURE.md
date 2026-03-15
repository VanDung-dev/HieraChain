# HieraChain Architecture

## 📋 Overview

HieraChain is a **multi-language blockchain infrastructure** designed for high-performance enterprise applications. The architecture follows a **layered approach** combining the strengths of Python and Rust:

| Component | Language | Purpose |
|:----------|:---------|:--------|
| **hierachain** | Python | Business logic, REST API, high-level abstractions |
| **hierachain-consensus** | Rust | High-performance consensus, cryptography |

---

## 📑 Table of Contents

- [🏗️ High-Level Architecture](#️-high-level-architecture)
- [📦 Project Structure](#-project-structure)
- [🏛️ Hierarchical Chain Architecture](#️-hierarchical-chain-architecture)
- [🔄 Data Flow Architecture](#-data-flow-architecture)
- [🔗 Inter-Language Communication](#-inter-language-communication)
- [⚙️ Consensus Mechanisms](#️-consensus-mechanisms)
- [🛡️ Zero Knowledge Proof (ZKP) Verification Layer](#️-zero-knowledge-proof-zkp-verification-layer)
- [🔐 Security Architecture](#-security-architecture)
- [📊 Performance Architecture](#-performance-architecture)
- [🌐 Network Architecture](#-network-architecture)
- [📈 Monitoring & Observability](#-monitoring--observability)
- [📄 License](#-license)

---

## 🏗️ High-Level Architecture

### System Overview

```mermaid
flowchart TB
    CLIENT["🖥️ <b>Client Applications</b><br/>Web Apps · Mobile · CLI · External Services"]
    
    API["🌐 <b>API Gateway Layer</b><br/>Python FastAPI · Arrow IPC"]
    
    CORE["⚙️ <b>Core Components</b><br/>hierachain · hierachain-consensus"]
    
    STORAGE["💾 <b>Data & Storage Layer</b><br/>SQL · In-Memory · World State · Arrow IPC"]

    CLIENT --> API --> CORE --> STORAGE
```

### API Gateway Detail

```mermaid
flowchart LR
    subgraph PY["🐍 Python FastAPI"]
        P1["REST API v1/v2"]
        P2["Blockchain Explorer"]
    end

```

### Core Components Detail

```mermaid
flowchart LR
    subgraph HP["🐍 hierachain"]
        direction TB
        HP1["Core blockchain logic"]
        HP2["Domain contracts"]
        HP3["Hierarchical chains"]
        HP4["Security policies"]
        HP1~~~HP2~~~HP3~~~HP4
    end

    subgraph HC["🦀 hierachain-consensus"]
        direction TB
        HC1["Block creation"]
        HC2["Hash & Merkle tree"]
        HC3["Digital signatures"]
        HC4["Consensus algorithms"]
        HC1~~~HC2~~~HC3~~~HC4
    end

    HP <-->|"PyO3 FFI"| HC
```

### Storage Layer Detail

```mermaid
flowchart LR
    S1[("SQL<br/>Backend")]
    S2[("In-Memory<br/>Storage")]
    S3[("World State<br/>Cache")]
    S4[("Arrow IPC<br/>Files")]

    S1 --- S2 --- S3 --- S4
```

---

## 📦 Project Structure

```
HieraChain Ecosystem/
├── hierachain/                    # 🐍 Python - Main Ledger
│   ├── adapters/                  # External adapters
│   ├── api/                       # REST API (FastAPI)
│   │   ├── v1/                    # API version 1
│   │   ├── v2/                    # API version 2
│   │   ├── server.py              # FastAPI server
│   │   └── blockchain_explorer.py # Explorer endpoints
│   ├── cli/                       # Command-line interface
│   ├── config/                    # Configuration management
│   ├── consensus/                 # Python consensus wrappers
│   │   └── ordering_service.py    # Transaction ordering
│   ├── core/                      # Core blockchain components
│   │   ├── block.py               # Block definitions
│   │   ├── blockchain.py          # Blockchain management
│   │   ├── caching.py             # Performance caching
│   │   ├── domain_contract.py     # Smart contracts
│   │   ├── parallel_engine.py     # Parallel execution
│   │   └── consensus/             # Consensus implementations
│   ├── domains/                   # Business domain logic
│   ├── error_mitigation/          # Error handling & recovery
│   ├── hierarchical/              # Hierarchical chain system
│   │   ├── channel.py             # Channel management
│   │   ├── main_chain.py          # Main chain logic
│   │   ├── sub_chain.py           # Sub-chain management
│   │   ├── hierarchy_manager.py   # Hierarchy coordination
│   │   └── consensus/             # BFT consensus
│   ├── integration/               # System integrations
│   ├── monitoring/                # Observability & metrics
│   ├── network/                   # Network layer
│   │   ├── zmq_transport.py       # ZeroMQ transport
│   │   └── secure_connection.py   # TLS connections
│   ├── risk_management/           # Risk assessment
│   ├── security/                  # Security & cryptography
│   ├── storage/                   # Data persistence
│   │   ├── memory_storage.py      # In-memory backend
│   │   ├── sql_backend.py         # SQL database
│   │   └── world_state.py         # State management
│   └── units/                     # Utility modules
│
├── hierachain-consensus/          # 🦀 Rust - High-Performance Core
│   ├── lib.rs                     # Library entry point + PyO3 module
│   ├── ffi.rs                     # Foreign Function Interface
│   ├── core/                      # Core components
│   │   ├── block.rs               # Block struct & operations
│   │   ├── blockchain.rs          # Blockchain management
│   │   ├── schemas.rs             # Data schemas
│   │   ├── utils.rs               # Utilities (hashing, Merkle)
│   │   ├── py_wrapper.rs          # Python bindings
│   │   └── consensus/             # Consensus algorithms
│   │       ├── poa.rs             # Proof of Authority
│   │       └── pof.rs             # Proof of Federation
│   ├── consensus/                 # Ordering services
│   │   └── ordering_service.rs    # Transaction ordering
│   ├── hierarchical/              # Hierarchical chains
│   │   ├── main_chain.rs          # Main chain
│   │   ├── sub_chain.rs           # Sub-chains
│   │   ├── bft.rs                 # BFT consensus
│   │   └── hierarchy_manager.rs   # Hierarchy management
│   ├── security/                  # Cryptography
│   │   └── signatures.rs          # Ed25519 signatures
│   ├── error_mitigation/          # Error handling
│   └── utils/                     # Helper functions
│
├── Cargo.toml                     # Rust dependencies
├── pyproject.toml                 # Python dependencies
└── Makefile                       # Build automation
```

---

## 🏛️ Hierarchical Chain Architecture

```mermaid
flowchart TB
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

    %% Connections
    MC --> SCA
    MC --> SCB
    MC --> SCC
    SCA --> CHA
    SCB --> CHB
    SCC --> CHC
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
    
    EX["🔄 <b>Parallel Execution</b><br/>Rust Consensus + Python Business Logic"]
    
    BF["✅ <b>Block Finalization</b><br/>Rust Core"]
    
    OUT["📤 <b>Output</b><br/>Network P2P · Storage · Monitoring"]

    CR --> EP --> MP --> WP --> EX --> BF --> OUT
```

---

## 🔗 Inter-Language Communication

### Unified Data Format: Apache Arrow

Python and Rust communicate using **Apache Arrow** as the common data format, enabling zero-copy data sharing:

```mermaid
flowchart TB
    subgraph ARROW["📦 Apache Arrow"]
        direction LR
        A1["Zero-Copy Memory"]
        A2["Columnar Format"]
        A3["Cross-Language"]
        A1~~~A2~~~A3
    end

    subgraph PY["🐍 Python"]
        PY1["PyArrow"]
    end

    subgraph RS["🦀 Rust"]
        RS1["arrow-rs"]
    end

    PY <--> ARROW
    RS <--> ARROW
```

| Language | Arrow Library | Integration Method |
|:---------|:--------------|:-------------------|
| **Python** | `pyarrow` | Native Python bindings |
| **Rust** | `arrow-rs` | PyO3 FFI + Arrow IPC |

### Python ↔ Rust (PyO3 FFI + Arrow)

```mermaid
flowchart TB
    subgraph PythonLayer["🐍 Python Layer"]
        PY1["PyArrow RecordBatch"]
        PY2["hierachain_consensus bindings"]
        PY1~~~PY2
    end

    FFI["PyO3 FFI<br/>(Arrow Memory Shared)"]

    subgraph RustLayer["🦀 Rust Layer"]
        R1["#[pyclass] Block"]
        R2["arrow-rs RecordBatch"]
        R3["#[pymodule] hierachain_consensus"]
        R1~~~R2~~~R3
    end

    PythonLayer --> FFI --> RustLayer
```

---

## ⚙️ Consensus Mechanisms

### Supported Algorithms

| Algorithm | Language | Use Case |
|:----------|:---------|:---------|
| **Proof of Authority (PoA)** | Rust | Private networks with trusted validators |
| **Proof of Federation (PoF)** | Rust | Multi-organization permissioned networks |
| **BFT Consensus** | Rust/Python | Byzantine fault-tolerant ordering |
| **Ordering Service** | Rust | Transaction ordering & batching |

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

- **ProofOfAuthority (PoA)**: Uses `_verify_block_zk_proof()` from `BaseConsensus`
- **ProofOfFederation (PoF)**: Uses `_verify_block_zk_proof()` from `BaseConsensus`
- **BFTConsensus**: Includes `_verify_operation_zk_proof()` in `_handle_pre_prepare`
- **OrderingService**: `EventCertifier.validate()` includes `_verify_zk_proof()` method

### Configuration

| Setting | Default | Description |
|:--------|:--------|:------------|
| `ENABLE_ZK_PROOFS` | `False` | Enable/disable ZK verification |
| `ZK_MODE` | `"mock"` | `"mock"` for development, `"production"` for real ZK |
| `ZK_VERIFICATION_KEY_PATH` | `""` | Path to ZoKrates verification key |
| `ZK_PROVING_KEY_PATH` | `""` | Path to ZoKrates proving key |

### Modes

- **Mock Mode**: Uses SHA-256 hashes to simulate ZK proofs (development)
- **Production Mode**: Uses **ZoKrates** for real ZK-SNARKs circuits

### Security Guarantees

- ✅ **Soundness**: Cannot forge a valid proof for an invalid state transition
- ✅ **Completeness**: Valid state transitions always produce valid proofs
- ✅ **Zero-Knowledge**: Proof reveals nothing about private transaction data
- ✅ **Non-Interactive**: No communication needed between prover and verifier
- ✅ **Succinct**: Proof size is constant regardless of transaction count

---

## 🔐 Security Architecture

```mermaid
flowchart TB
    subgraph Security["Security Layers"]
        TS["🔒 <b>Transport</b><br/>───────────<br/>TLS 1.3<br/>mTLS<br/>ZMQ Curve"]
        CR["🔑 <b>Crypto (Rust)</b><br/>───────────<br/>Ed25519<br/>SHA-256<br/>Merkle Tree"]
        AC["👤 <b>Access Control</b><br/>───────────<br/>Role-based<br/>Organization<br/>Channel"]
        TS ~~~ CR ~~~ AC
    end

    subgraph DataSecurity["Data & Connection Security"]
        PD["📁 <b>Data Collections</b><br/>───────────<br/>Encryption<br/>Hash Only<br/>Access Rules"]
        SC["🔗 <b>Connections</b><br/>───────────<br/>Peer Auth<br/>Node Verify<br/>Key Rotation"]
        EM["🛡️ <b>Error Mitigation</b><br/>───────────<br/>Fault Tolerance<br/>Recovery"]
        PD ~~~ SC ~~~ EM
    end

    Security --> DataSecurity
```

---

## 📊 Performance Architecture

```mermaid
flowchart TB
    subgraph Performance["Performance Optimization Strategies"]
        L1["🔄 <b>Zero-Copy Transfer</b><br/>Arrow IPC<br/>───────────<br/>Eliminates serialization<br/>overhead across layers"]
        L2["🔀 <b>Parallel Processing</b><br/>Worker Pool<br/>───────────<br/>Concurrent execution<br/>Configurable workers"]
        L3["🔐 <b>Native Crypto</b><br/>Rust<br/>───────────<br/>Ed25519 signatures<br/>SHA-256, Merkle trees"]
        L1 ~~~ L2 ~~~ L3
    end

    subgraph Batching["Batching & Caching"]
        L4["📦 <b>Batch Operations</b><br/>Rust<br/>───────────<br/>batch_create_blocks<br/>batch_calculate_hashes"]
        L5["📋 <b>TX Batching</b><br/>Mempool<br/>───────────<br/>Groups transactions<br/>Efficient processing"]
        L6["💾 <b>Cache Layer</b><br/>Python<br/>───────────<br/>In-memory caching<br/>Frequently accessed data"]
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
            P1E["Network Engine (P2P/ZMQ)"]
            P1A["Python API"]
            P1R["Rust Core"]
            P1E ~~~ P1A ~~~ P1R
        end
        subgraph Peer2["Peer Node 2"]
            P2E["Network Engine (P2P/ZMQ)"]
            P2A["Python API"]
            P2R["Rust Core"]
            P2E ~~~ P2A ~~~ P2R
        end
        subgraph Peer3["Peer Node 3"]
            P3E["Network Engine (P2P/ZMQ)"]
            P3A["Python API"]
            P3R["Rust Core"]
            P3E ~~~ P3A ~~~ P3R
        end
    end

    subgraph Protocols["Message Protocols"]
        MP1["ZeroMQ (Fast)"]
        MP2["HTTP/REST (Structured)"]
        MP3["Arrow IPC (Bulk)"]
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

---

## 📄 License

Dual licensed under [Apache-2.0](LICENSE-APACHE) or [MIT](LICENSE-MIT).

---

*Last updated: 2026-01-12*
