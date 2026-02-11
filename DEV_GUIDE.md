# Developer Guide

This guide contains all the information developers need to work with the HieraChain framework.

---

## Installation

### Prerequisites

- Python 3.10, 3.11, 3.12, or 3.13
- `pip` (bundled with Python)

### Create Virtual Environment

It is **strongly recommended** to use a virtual environment (`.venv`) to isolate project dependencies.

**Windows (PowerShell):**

```powershell
# Create venv
python -m venv .venv

# Activate venv
.venv\Scripts\Activate.ps1

# Verify (should point to .venv)
Get-Command python | Select-Object Source
```

**Linux / macOS:**

```bash
# Create venv
python3 -m venv .venv

# Activate venv
source .venv/bin/activate

# Verify (should point to .venv)
which python
```

> **Note:** All commands below assume the virtual environment is **activated**.
> To deactivate, run `deactivate`.

### Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Development & testing dependencies
pip install -r requirements_dev.txt

# Install the package in development mode
pip install -e .
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
>
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

### Docker Stress Testing

Run stress tests in Docker containers with 4 HieraChain nodes (1 CPU, 1GiB RAM each):

- Build and run stress tests with HTML report:

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html
    ```

- Run real network stress tests (sends actual HTTP requests to nodes):

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester python -m pytest tests/stress/test_real_network.py -v -s
    ```

- Run without HTML report:

    ```bash
    docker compose -f docker/docker-compose.test.yml --profile stress-test run stress-tester
    ```

- Stop and clean up containers:

    ```bash
    docker compose -f docker/docker-compose.test.yml down --remove-orphans
    ```

Reports are saved to `log/report/` directory.

### Kubernetes Stress Testing

Run stress tests in Kubernetes
> **Recommendation:** Use Docker Compose for local dev. Use Kubernetes when you need a production-like environment.

**Quick Start:**

```bash
# Build image & deploy
docker build --no-cache -t hierachain:latest -f docker/Dockerfile .
kind create cluster --name hiera-cluster
kind load docker-image hierachain:latest --name hiera-cluster
kubectl apply -k docker/k8s/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=hierachain -n hierachain --timeout=120s

# Expose the API to local host
kubectl port-forward service/hierachain-api 32661:2661 -n hierachain --address 0.0.0.0

# Test API  
curl http://localhost:32661/api/v1/health

# Run stress test
docker compose -f docker/docker-compose.k8s-stress.yml --profile stress-test run --build stress-tester python -m pytest tests/stress/ -v --html=/app/log/report/stress_test_report.html --self-contained-html

# Cleanup
kubectl delete -k docker/k8s/
kind delete cluster --name hiera-cluster
```

---

## Documentation

The project documentation is built using [MkDocs](https://www.mkdocs.org/) with the [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme.

### Serve Locally

To run the documentation server locally with live reloading:

```bash
mkdocs serve -f docs/mkdocs.yml
```

Open your browser at `http://127.0.0.1:8000` to view the documentation.

### Build Static Site

To build the static HTML site (output to `site/` directory):

```bash
mkdocs build -f docs/mkdocs.yml
```

### Generate API Reference Docs (.py → .md)

API reference documentation is **auto-generated** from Python docstrings using [`pydoc-markdown`](https://pypi.org/project/pydoc-markdown/).

#### Prerequisites

Make sure `pydoc-markdown` is installed inside the `.venv`:

```bash
pip install pydoc-markdown
```

#### Generate All Modules

Run the generation script (must use the `.venv` Python):

**Windows (PowerShell):**

```powershell
$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe scripts/generate_api_docs.py
```

**Linux / macOS:**

```bash
PYTHONIOENCODING=utf-8 .venv/bin/python scripts/generate_api_docs.py
```

Generated Markdown files are saved to `docs/vi/reference/`.

#### Generate a Specific Module

Use a module shorthand or full path:

```bash
# By shorthand (matches hierachain.core.block)
.venv/Scripts/python.exe scripts/generate_api_docs.py block

# By full module path
.venv/Scripts/python.exe scripts/generate_api_docs.py hierachain.core.block

# Dry-run (preview without writing files)
.venv/Scripts/python.exe scripts/generate_api_docs.py block --dry-run
```

#### How It Works

```text
hierachain/core/block.py          (Python source with Vietnamese docstrings)
        │
        ▼  pydoc-markdown parses docstrings
scripts/generate_api_docs.py       (adds YAML frontmatter + metadata)
        │
        ▼
docs/vi/reference/core/block.md    (Markdown ready for MkDocs)
```

> **Important:** After modifying docstrings in `.py` files, you must **re-run** the
> generation script to update the corresponding `.md` files.
> The `PYTHONIOENCODING=utf-8` environment variable is **required** on Windows
> to correctly handle Vietnamese characters.

#### Configuration

The `pydoc-markdown` configuration is in [`pydoc-markdown.yml`](pydoc-markdown.yml).
The module mapping (icon, description, output directory) is defined in
[`scripts/generate_api_docs.py`](scripts/generate_api_docs.py) → `MODULES` dict.

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
