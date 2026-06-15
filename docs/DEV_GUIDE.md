# Developer Guide

This guide contains the essential information developers need to get started with the HieraChain Ledger.

For detailed documentation on specific topics, please refer to the links below.

---

## Installation

### Prerequisites

* Python 3.10, 3.11, 3.12, or 3.13
* `pip` (bundled with Python)

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

#### Using `pip` (traditional method)

```bash
# Install all dependencies (core + dev + test)
pip install -e ".[dev]"
```

#### Using `uv` (recommended, modern fast package manager)

`uv` is a modern, extremely fast Python package manager written in Rust. It's **10-100x faster** than pip for dependency resolution and installation.

**Install uv first (if not available):**

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Setup project with uv:**

```bash
# Initialize virtual environment (auto detected)
uv venv

# Activate venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows

# Install ALL dependencies automatically (core + dev)
uv sync

# Or install only core + dev extras (if you need dev tools like pytest)
uv sync --extra dev

# ✅ These commands replace all 3 pip commands above
# They read pyproject.toml, resolve dependencies, install everything in dev mode
```

This will set up your environment to work with the Ledger.

---

## Running Server

```bash
python -m hierachain.api.server
```

Server will start at `http://localhost:2661` with API docs at `http://localhost:2661/docs`.

---

## Using the Package

After installation, you can import components from the package:

```python
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
```

---

## Detailed Documentation by Topic

For more detailed information on specific topics, please refer to the following README files:

### 🎯 Running Demos
**File:** [`demo/README.md`](../demo/README.md)

Covers all demo scripts including:

* Main Ledger Demonstration (hierarchical chains, MSP, channels, private data)
* Blockchain Explorer Dashboard
* IPFS Integration for off-chain storage
* Key Backup & Recovery
* ZeroMQ BFT Consensus

Quick start:
```bash
python demo/demo.py
```

---

### 🧪 Running Tests

**File:** [`tests/README.md`](../tests/README.md)

Covers all test types:

* Unit tests, Integration tests, Scenario tests
* Benchmark tests
* Docker & Kubernetes stress testing
* Test fixtures and individual test file execution

Quick start:

```bash
python -m pytest tests/unit -v
```

---

### 🐳 Docker & Kubernetes Stress Testing

**File:** [`docker/README.md`](../docker/README.md)

Dedicated to performance benchmarking and stability testing:

* Docker Compose setup (4-node cluster)
* Kubernetes (Kind) setup with resource limits
* Stress test execution and reports
* Configuration tuning

Quick start:

```bash
docker/setup-docker-compose.sh
docker/run-stress-docker-compose.sh
```

---

### 📝 Documentation

**File:** [`docs/README.md`](../docs/README.md)

Covers documentation building with Zensical:

* Local serve with live reload
* Static site build for production
* Multi-language support (Vietnamese, English, Russian)
* Custom domain configuration for GitHub Pages

Quick start:

```bash
zensical serve
```

---

### 🛠️ Developer Scripts

**File:** [`scripts/README.md`](../scripts/README.md)

Contains utilities for development and analysis:

* Benchmarking (hashing, throughput)
* Static code analysis (security, quality, compliance)
* Security probes (16 different vulnerability tests)
* Storage verification

Quick start:

```bash
python scripts/benchmark_hashing.py
python -m scripts.static_analysis
```

---

## Quick Reference

| Task | Command | Details in |
|------|---------|------------|
| Install all deps | `uv sync` | This file (Installation section) |
| Install core + dev | `uv sync --extra dev` | This file (Installation section) |
| Run API server | `python -m hierachain.api.server` | This file (Running Server section) |
| Run demos | `python demo/demo.py` | [`demo/README.md`](../demo/README.md) |
| Run tests | `python -m pytest tests/unit -v` | [`tests/README.md`](../tests/README.md) |
| Stress test (Docker) | `docker/run-stress-docker-compose.sh` | [`docker/README.md`](../docker/README.md) |
| Build documentation | `zensical build` | [`docs/README.md`](../docs/README.md) |
| Static analysis | `python -m scripts.static_analysis` | [`scripts/README.md`](../scripts/README.md) |
