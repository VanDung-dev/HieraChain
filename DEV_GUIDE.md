# Developer Guide

This guide contains all the information developers need to work with the HieraChain framework.

---

## Installation

### Prerequisites

- Python 3.10, 3.11, 3.12, or 3.13

### Quick Start

- Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

- Install development dependencies

    ```bash
    pip install -r requirements_dev.txt
    ```

- Install the package:

    ```bash
    pip install -e .  # Development mode
    pip install .     # Production mode
    ```

This will set up your environment to work with the framework.

## Running server

```bash
python -m hierachain.api.server
```

---

## Using the package

After installation, you can import components from the package:

```python
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
```

---

## Running Demos

The demo files are located in the `demo/` directory. Before running demos, ensure you have installed the package and its dependencies.

- **Main Framework Demonstration** - Showcases core HieraChain features including hierarchical chains, MSP, channels, and private data:

    ```bash
    python demo/demo.py
    ```

- **Key Backup and Recovery Demonstration** - Demonstrates cryptographic key backup and recovery functionality:

    ```bash
    python demo/demo_key_backup.py
    ```

- **ZeroMQ BFT Consensus Demonstration** - Demonstrates Byzantine Fault Tolerance consensus with ZeroMQ networking:

    ```bash
    python demo/demo_zmq_consensus.py
    ```

> **Note**: For demos that create data files, you may want to clean up old data before running:
> ```bash
> rm -rf demo/data demo/hierachain.db 2>/dev/null
> ```

---

## Running Tests

> **WARNING**: Running all tests simultaneously may cause failures due to resource constraints. It is recommended to run tests per test file instead of grouping them by directories to ensure more accurate and reliable results.

- To run all unit tests:

    ```bash
    python -m pytest tests/unit -v
    ```

- To run all integration tests:

    ```bash
    python -m pytest tests/integration -v
    ```

- To run all scenario tests:
    ```bash
    python -m pytest tests/scenarios -v
    ```

- To run only benchmark tests:

    ```bash
    python -m pytest tests --benchmark-only -v --benchmark-save=benchmark_report
    python -m pytest tests --benchmark-only -v --benchmark-histogram=benchmark_report
    ```

- To run all tests:

    ```bash
    python -m pytest tests -v
    ```

---

## Developer Scripts

The `scripts/` directory contains additional utilities for development and benchmarking.

### Static Analysis

- To run static code analysis:

    ```bash
    python -m scripts.static_analysis
    ```

- To run static code analysis with text output:

    ```bash
    python -m scripts.static_analysis --format text
    ```

- To run static code analysis and save results to a file:

    ```bash
    python -m scripts.static_analysis --output analysis_report.json
    python -m scripts.static_analysis --format text --output analysis_report.txt
    ```

### Benchmarking

- **Hashing Performance Benchmark** - Compares Merkle tree hashing vs traditional JSON serialization:

    ```bash
    python scripts/benchmark_hashing.py
    ```

- **Throughput Benchmark** - Measures event processing throughput of the OrderingService:

    ```bash
    python scripts/benchmark_throughput.py --events 1000 --workers 4 --batch-size 100
    ```

    Options:
    - `--events`: Number of events to process (default: 1000)
    - `--workers`: Number of worker threads (default: auto-detected)
    - `--batch-size`: Events per block (default: 100)

### Storage Verification

- **Verify Storage Persistence** - Validates SQLite storage backend persistence:

    ```bash
    python scripts/verify_storage.py
    ```

---
