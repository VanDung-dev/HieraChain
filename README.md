# HieraChain - The Hierarchical Blockchain Enterprise Ledger

![Python Versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE-APACHE)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE-MIT)
[![PyPI version](https://img.shields.io/pypi/v/HieraChain.svg)](https://pypi.org/project/HieraChain/)

**English** | [Tiếng Việt](README.vi.md)

## Overview

HieraChain is an enterprise ledger built on hierarchical blockchain technology, designed specifically for business applications without any cryptocurrency concepts. Rather than being a general-purpose blockchain platform focused on digital currencies, HieraChain provides a secure, hierarchical ledger structure for managing business operations and processes.

This ledger implements a multi-layer hierarchical architecture where Main Chains supervise Sub-Chains, enabling scalable and secure business process management. All operations within the system are referred to as "events" rather than "transactions," emphasizing its focus on business applications.

## Key Features

* **Hierarchical Structure**: Multi-layer architecture with Main Chains (supervisors) and Sub-Chains (domain experts).
* **Consensus Mechanisms**: Supports Proof of Authority (PoA), Proof of Federation (PoF), and Byzantine Fault Tolerant (BFT) consensus.
* **High Performance**: Columnar storage with Apache Arrow, hybrid caching, and parallel event processing.
* **Reliability & Recovery**: Durable transaction journaling, automated failure recovery, and state rollback capabilities.
* **Comprehensive Security Architecture**: An omnipresent, enterprise-grade security philosophy extending across the entire system lifecycle (not just a single module), built on 6 core pillars:

    * **Authorization** (ABAC Policy Engine & MSP)
    * **Lockdown & Logging** (Quorum-based Voting & Tamper-evident Logs)
    * **Fault-tolerance** (BFT & Federation)
    * **Risk Analyzer** (Real-time Z-score activity monitoring)
    * **Encryption** (AES-256-GCM for storage, Ed25519 for signatures)
    * **Decentralized Zero-Knowledge Proofs** (ZK Verifier for trustless chain anchoring)

## Documentation

Comprehensive documentation is available at our official website **[docs.hierachain.org](https://docs.hierachain.org/)**:

* [Getting Started](https://docs.hierachain.org/getting-started/install/) - Installation and basic setup
* [Architecture](https://docs.hierachain.org/architecture/overview/) - System design and hierarchical model
* [Core Modules](https://docs.hierachain.org/modules/core/) - Detailed breakdown of system components
* [Guides & How-To](https://docs.hierachain.org/how-to/integrate-web2/) - Step-by-step implementation guides
* [API Reference](https://docs.hierachain.org/reference/code-map/) - REST API and configuration details

## Quick Start

### Installation

**Via PIP (recommended)**

```bash
pip install HieraChain
```

**From source (for development)**

*Traditional `pip` method:*

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain
python -m venv venv
source venv/bin/activate  # Linux/macOS (or venv\Scripts\activate on Windows)

# Install dependencies and project in dev mode
pip install -e .[dev]
```

*Modern fast method with `uv` (recommended):*

```bash
git clone https://github.com/VanDung-dev/HieraChain.git
cd HieraChain

# Install uv if not installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Auto create venv + install ALL dependencies in one command
uv sync

source .venv/bin/activate
```

### Basic Usage

```python
from hierachain.hierarchical import HierarchyManager

manager = HierarchyManager()
manager.create_sub_chain("supply_chain")

# Add an event
manager.add_event("supply_chain", {
    "entity_id": "PROD-001",
    "event": "production_complete",
    "timestamp": 1703088000.0,
    "details": {"quantity": 100}
})

# Submit proof to main chain
manager.submit_proof("supply_chain")
```

API Server:

```bash
python -m hierachain
```

API available at `http://localhost:2661/docs`

## Technical Specifications

| Metric | Value                  |
|--------|------------------------|
| Test Cases | >700                   |
| Python Support | 3.10, 3.11, 3.12, 3.13 |
| Consensus Types | PoA, PoF, BFT          |
| Signature Algorithm | Ed25519                |
| Encryption | AES-256-GCM            |

## License

This project is dual licensed under either the [Apache-2.0 License](LICENSE-APACHE) or the [MIT License](LICENSE-MIT). You may choose either license.
