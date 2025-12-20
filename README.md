# HieraChain Framework

![Python Versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE-APACHE)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE-MIT)
![Version](https://img.shields.io/badge/version-0.0.0.dev5-orange)
![Tests](https://img.shields.io/badge/tests-371%20passed-green)

**English** | [Tiếng Việt](README_vi.md)

## Overview

HieraChain is an advanced enterprise blockchain framework designed specifically for business applications without any cryptocurrency concepts. Unlike traditional blockchain platforms focused on digital currencies, HieraChain focuses on providing a secure, hierarchical structure for managing business operations and processes.

The framework implements a multi-layer architecture where Main Chains supervise Sub-Chains, enabling scalable and secure business process management. All operations within the framework are referred to as "events" rather than "transactions," emphasizing its focus on business applications.

## Core Architecture

### Hierarchical Structure

The framework follows a hierarchical architecture consisting of:

1. **Main Chain (Supervisor)**
   - Acts as the root authority in the system
   - Stores only cryptographic proofs from Sub-Chains, not detailed domain data
   - Maintains the integrity of the entire hierarchical system
   - Provides proof verification and chain coordination

2. **Sub-Chains (Domain Experts)**
   - Handle domain-specific business operations
   - Store detailed domain events and data
   - Submit cryptographic proofs to the Main Chain
   - Operate independently but are supervised by the Main Chain

```
Main Chain (Supervisor)
├── Sub-Chain 1 (Domain A)
├── Sub-Chain 2 (Domain B)
└── Sub-Chain 3 (Domain C)
```

### Key Design Principles

- **Event-Based Model**: Business operations are represented as "events" rather than cryptocurrency transactions
- **Proof Submission**: Sub-Chains submit cryptographic proofs to the Main Chain for verification
- **Data Segregation**: Detailed domain data stays in Sub-Chains; only proofs reach the Main Chain
- **Entity Identification**: Entities are identified through metadata fields
- **Scalability**: The hierarchical structure enables horizontal scaling across multiple domains

## Module Structure

### Core (`hierachain/core/`)

The foundation of HieraChain:

| Component | Description |
|-----------|-------------|
| `block.py` | Block structure with Apache Arrow storage |
| `blockchain.py` | Base blockchain implementation |
| `caching.py` | L1/L2 caching system (LRU, LFU, TTL policies) |
| `parallel_engine.py` | Parallel processing engine |
| `domain_contract.py` | Smart contract-like domain logic |
| `consensus/` | Proof of Authority & Proof of Federation |

### Hierarchical (`hierachain/hierarchical/`)

Multi-chain management:

| Component | Description |
|-----------|-------------|
| `main_chain.py` | Root authority storing proofs |
| `sub_chain.py` | Domain-specific chains |
| `hierarchy_manager.py` | Coordination between chains |
| `channel.py` | Private channels for organizations |
| `multi_org.py` | Multi-organization support |
| `private_data.py` | Private data collections |
| `consensus/bft_consensus.py` | Byzantine Fault Tolerant consensus |

### Security (`hierachain/security/`)

Enterprise-grade security:

| Component | Description |
|-----------|-------------|
| `msp.py` | Membership Service Provider |
| `certificate.py` | X.509 certificate management |
| `key_manager.py` | Ed25519 key management |
| `key_provider.py` | Secure key storage (FileVault) |
| `key_backup_manager.py` | Key backup & recovery |
| `policy_engine.py` | Access control policies |
| `verify_api_key.py` | API key authentication |
| `identity.py` | Identity management |

### Consensus (`hierachain/consensus/`)

Ordering and consensus:

| Component | Description |
|-----------|-------------|
| `ordering_service.py` | Event ordering with hybrid cache |

### API (`hierachain/api/`)

RESTful interfaces:

| Version | Description |
|---------|-------------|
| `v1/` | Core endpoints for chain management |
| `v2/` | Enhanced endpoints with ordering service |
| `blockchain_explorer.py` | Chain exploration API |

### Error Mitigation (`hierachain/error_mitigation/`)

Fault tolerance:

| Component | Description |
|-----------|-------------|
| `recovery_engine.py` | Network, consensus, backup recovery |
| `rollback_manager.py` | State rollback capabilities |
| `journal.py` | Transaction journal (durable logging) |
| `validator.py` | Data validation rules |
| `error_classifier.py` | Error classification & priority |

### Risk Management (`hierachain/risk_management/`)

| Component | Description |
|-----------|-------------|
| `risk_analyzer.py` | Risk detection & scoring |
| `mitigation_strategies.py` | Automated mitigation |
| `audit_logger.py` | Comprehensive audit logging |

### Monitoring (`hierachain/monitoring/`)

| Component | Description |
|-----------|-------------|
| `performance_monitor.py` | System & blockchain metrics |

### Storage (`hierachain/storage/`)

| Component | Description |
|-----------|-------------|
| `sql_backend.py` | SQLite/PostgreSQL storage |
| `memory_storage.py` | In-memory storage |
| `world_state.py` | World state management |

### Integration (`hierachain/integration/`)

| Component | Description |
|-----------|-------------|
| `erp_framework.py` | ERP system integration |
| `enterprise.py` | Enterprise connectors |

### Adapters (`hierachain/adapters/`)

| Component | Description |
|-----------|-------------|
| `storage/file_storage.py` | File-based storage adapter |
| `storage/redis_storage.py` | Redis storage adapter |

### Config (`hierachain/config/`)

| Component | Description |
|-----------|-------------|
| `settings.py` | Python-based configuration |

## Key Features

### Consensus Mechanisms

- **Proof of Authority (PoA)**: Static validator-based consensus for centralized deployments
- **Proof of Federation (PoF)**: Dynamic consortium-based consensus
- **BFT Consensus**: Byzantine Fault Tolerant consensus with view change support

### Security

- **Ed25519 Signatures**: Modern elliptic curve cryptography
- **AES-256-GCM Encryption**: For private data and backups
- **MSP (Membership Service Provider)**: Certificate-based authentication
- **API Key Authentication**: With revocation support

### Performance

- **Apache Arrow**: Columnar storage for blocks
- **Hybrid Cache**: L1 memory + L2 persistent cache
- **Parallel Processing**: Multi-threaded event processing
- **Bounded History**: Memory-efficient block history with DB fallback

### Reliability

- **Transaction Journal**: Durable event logging
- **Rollback Manager**: State restoration capabilities
- **Recovery Engines**: Automated failure recovery
- **371 Test Cases**: Comprehensive test coverage including fuzzing

## Quick Start

### Installation

> **Note**: HieraChain is currently in development. PyPI release is planned for Q1 2026.

#### Local Installation

```bash
# Clone the repository
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Basic Usage

```python
from hierachain.hierarchical import HierarchyManager

# Create hierarchy manager
manager = HierarchyManager()

# Create a sub-chain
manager.create_sub_chain("supply_chain")

# Add an event
event_id = manager.add_event("supply_chain", {
    "entity_id": "PROD-001",
    "event": "production_complete",
    "timestamp": 1703088000.0,
    "details": {"quantity": 100}
})

# Submit proof to main chain
proof = manager.submit_proof("supply_chain")
```

### Running the API Server

```bash
python -m hierachain.api.server
```

API available at `http://localhost:2661/docs`

## Use Cases

HieraChain is ideal for enterprise applications requiring:

- Supply chain management
- Regulatory compliance tracking
- Audit trail maintenance
- Multi-department workflow coordination
- Secure inter-organization data sharing
- Quality assurance processes
- Asset tracking and management

## Technical Specifications

| Metric | Value |
|--------|-------|
| Source Files | 96 Python files |
| Lines of Code | ~30,000 |
| Test Cases | 371 |
| Python Support | 3.10, 3.11, 3.12, 3.13 |
| Consensus Types | PoA, PoF, BFT |
| Signature Algorithm | Ed25519 |
| Encryption | AES-256-GCM |

## Configuration

Configuration is managed through `hierachain/config/settings.py`:

```python
from hierachain.config import settings

# Access settings
print(settings.API_PORT)  # 2661
print(settings.CONSENSUS_TYPE)  # proof_of_authority
print(settings.BFT_ENABLED)  # True
```

Environment variables:

- `HRC_ENV`: Environment (dev/test/product)
- `HRC_CONSENSUS_TYPE`: Consensus type
- `HRC_AUTH_ENABLED`: Enable API authentication
- `LOG_LEVEL`: Logging level

## License

This project is dual licensed under either the [Apache-2.0 License](LICENSE-APACHE) or the [MIT License](LICENSE-MIT). You may choose either license.

---
