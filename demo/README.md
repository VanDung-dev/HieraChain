# HieraChain Demo Scripts

This directory contains demonstration scripts for exploring HieraChain features and capabilities.

---

## Demo Scripts Overview

```
demo/
├── demo.py                    # Main demo - Core features (hierarchical chains, MSP, channels)
├── demo_explorer.py           # Web-based blockchain explorer dashboard
├── demo_ipfs.py               # IPFS integration for off-chain storage
├── demo_key_backup.py         # Key backup and recovery functionality
├── demo_zmq_consensus.py      # BFT consensus over ZeroMQ network
├── index.html                 # Frontend dashboard for explorer
└── config/                    # Demo configuration files
```

---

## Prerequisites

Before running demos, ensure you have installed all dependencies:

```bash
# Install core dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements_dev.txt

# Install the package in development mode
pip install -e .
```

---

## Available Demos

### 1. Main Demo (`demo.py`)

Demonstrates the core features of HieraChain:

* **Main Chain and Sub-Chain** creation and management
* **Entity registration** and lifecycle management
* **Business operations** (resource allocation, quality checks, approvals)
* **Proof submissions** from Sub-Chains to Main Chain
* **Entity tracing** across multiple chains
* **Cross-chain validation** and integrity checking
* **Membership Service Provider (MSP)** integration
* **Channel-based data isolation**
* **Private data collections**

**Run:**

```bash
python demo/demo.py
```

**Output:**

* Console output showing all operations
* Log file saved to `log/demo_log_<timestamp>.log`
* Generated data files in `demo/data/` for the explorer

---

### 2. Explorer Dashboard (`demo_explorer.py`)

Provides a web-based dashboard for visualizing blockchain data:

* **Blockchain overview** (blocks, events, nodes)
* **Entity traceability** visualization
* **REST API** for data access

**Run:**

```bash
# First, run the main demo to generate data
python demo/demo.py

# Then start the explorer server
python demo/demo_explorer.py
```

**Access:**

* Dashboard: http://127.0.0.1:8000
* API docs: http://127.0.0.1:8000/docs

---

### 3. IPFS Integration (`demo_ipfs.py`)

Demonstrates IPFS integration for off-chain storage:

* **Direct IPFS client** usage (upload/download/encryption)
* **Storing large event details** in IPFS with CID references on-chain
* **Resolving IPFS CIDs** to actual data during retrieval
* **Private data** and contract implementation storage in IPFS
* **Explorer visualization** with IPFS indicators

> **Note:** Requires IPFS daemon to be running. If not available, a mock client is used.

**Run:**

```bash
# Start IPFS daemon (if available)
ipfs daemon &

# Run the demo
python demo/demo_ipfs.py
```

---

### 4. Key Backup & Recovery (`demo_key_backup.py`)

Showcases the key backup and recovery functionality:

* **RSA key pair generation**
* **Key backup** with AES-256-GCM encryption
* **Key recovery** with integrity verification (SHA-512)
* **Multiple backup locations** (primary vault, secondary cloud)
* **Error handling** for backup and restore operations

**Run:**

```bash
python demo/demo_key_backup.py
```

---

### 5. ZeroMQ BFT Consensus (`demo_zmq_consensus.py`)

Demonstrates Byzantine Fault Tolerance consensus over a ZeroMQ network:

* **Multi-node network** setup using AsyncIO and ZeroMQ
* **BFT consensus** with message passing
* **Byzantine fault tolerance** (tolerates f faulty nodes with 3f+1 total)
* **Real-time consensus** visualization in console

**Run:**

```bash
python demo/demo_zmq_consensus.py
```

---

## Quick Reference

| Demo | Command | Description |
|------|---------|-------------|
| Main features | `python demo/demo.py` | Hierarchical chains, MSP, channels |
| Explorer | `python demo/demo_explorer.py` | Web dashboard for blockchain data |
| IPFS | `python demo/demo_ipfs.py` | Off-chain storage with IPFS |
| Key backup | `python demo/demo_key_backup.py` | Key backup and recovery |
| BFT consensus | `python demo/demo_zmq_consensus.py` | BFT consensus over ZeroMQ |

---

## Notes

* **Demo data** is generated in the `demo/data/` directory
* **Log files** are saved to the `log/` directory
* **Database** files may be created in `demo/hierachain.db`
* Clean demo data: `rm -rf demo/data demo/hierachain.db 2>/dev/null`

---

## Related Documentation

* **Tests**: See [`tests/README.md`](../tests/README.md) for test execution
* **Docker**: See [`docker/README.md`](../docker/README.md) for containerized deployment
* **Scripts**: See [`scripts/README.md`](../scripts/README.md) for development utilities
* **Development Guide**: See [`docs/DEV_GUIDE.md`](../docs/DEV_GUIDE.md) for full guide
