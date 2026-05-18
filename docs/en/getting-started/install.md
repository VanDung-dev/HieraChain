---
title: Installing HieraChain
description: Guide to installing HieraChain from source for development environment.
icon: material/download
---

# Installing HieraChain

This document guides you through various ways to install and set up HieraChain.

## Installation via PIP (Recommended)

This is the fastest and simplest way to start using HieraChain as a library or running the server.

```bash
# Note: The project is currently in development phase, source installation is recommended.
pip install .
```

After installation, you can verify with:

```bash
hrc --help
```

### Using `uv` (Recommended for High Performance)

`uv` is a modern Python package manager written in Rust, 10-100x faster than pip.

**Installing uv:**
=== "Linux/macOS"
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
=== "Windows (PowerShell)"
    ```powershell
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

**Setting up project with uv:**
```bash
# Create virtual environment and sync base dependencies
uv sync

# Install with specific tool groups (extras):
uv sync --extra dev --extra doc

# Or install ALL extras available in the project:
uv sync --all-extras

# If you only want production environment (skip dev dependencies):
uv sync --no-dev

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows
```

## Installation from Source (For Developers)

If you want to contribute to the project or customize the source code, follow these steps:

1. Clone repository and create virtual environment

    ```bash
    git clone https://github.com/VanDung-dev/HieraChain.git
    cd HieraChain
    ```
    
    Create & activate venv
    
    === "Linux/macOS"
    
        ```bash
        python -m venv .venv
        source .venv/bin/activate
        ```
    
    === "Windows (PowerShell)"
    
        ```powershell
        python -m venv .venv
        .venv\Scripts\Activate.ps1
        ```

2. Install dependencies and set up development mode

    === "Using UV (Recommended)"
    
        ```bash
        # Sync dependencies with dev environment
        uv sync --extra dev
        
        # Or if you want to add doc, test
        uv sync --all-extras
        ```
    
    === "Using pip"
    
        ```bash
        # Install all dependencies (production + dev + test) in editable mode
        pip install -e ".[dev]"
        ```

3. Verify installation

    ```bash
    # Check version via importlib.metadata
    python -c "import importlib.metadata as m; print(m.version('HieraChain'))"
    
    # Check CLI is in PATH
    hrc --help
    
    # Start API server (optional)
    python -m hierachain.api.server
    ```

If the server starts successfully, you can open the interactive documentation at: `http://localhost:2661/docs`.

## Running Tests

!!! warning "Warning"

    Do not run all tests simultaneously to avoid resource conflicts. Recommended to run per file or per unit/integration directory.

```bash
# Run unit tests
python -m pytest tests/unit -v

# Run integration tests
python -m pytest tests/integration -v

# Run scenarios tests
python -m pytest tests/scenarios -v
```

## Running the Server

To start the HieraChain API server:

```bash
python -m hierachain.api.server
```

## Library Usage

After installation, you can import components from the package in your Python code:

```python
from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain
```

## Running Demos

Demo files are in the `demo/` directory. Before running, ensure you have installed the package and dependencies.

* **Main Demo** - Illustrates core features: hierarchical chains, MSP, channels, private data:

    ```bash
    python demo/demo.py
    ```

* **Key Backup & Recovery Demo** - Illustrates key backup/recovery functionality:

    ```bash
    python demo/demo_key_backup.py
    ```

* **ZeroMQ BFT Consensus Demo** - Illustrates Byzantine Fault Tolerance consensus over ZeroMQ:

    ```bash
    python demo/demo_zmq_consensus.py
    ```

!!! note "Note"

    To clean up old data before re-running demos:

    === "Linux/macOS"

        ```bash
        rm -rf demo/data demo/hierachain.db 2>/dev/null
        ```

    === "Windows (PowerShell)"

        ```powershell
        Remove-Item -Recurse -Force demo/data, demo/hierachain.db -ErrorAction SilentlyContinue
        ```

## Documentation

The project uses [Zensical](https://zensical.org/) to build documentation.

### Requirements

Ensure Zensical is installed (docs dependencies):

=== "Using UV"

    ```bash
    uv sync --extra doc
    ```

=== "Using pip"

    ```bash
    pip install -e ".[doc]"
    ```

### Running Documentation Server (Local)

To view documentation with live-reload:

```bash
zensical serve
```

Access `http://127.0.0.1:8000`.

### Building Static Site

To build static HTML (to `site/` directory):

```bash
zensical build
```

## Uninstall / Clean Environment

```bash
pip uninstall -y HieraChain
deactivate  # exit virtual environment (if active)
```

## Troubleshooting

* `hrc` command not found: check that venv is activated and `pip install -e .` succeeded.
* Dependency compilation errors: ensure appropriate build tools exist (e.g., on Windows install Build Tools for Visual Studio if needed).
* API port 2661 busy: adjust configuration in `hierachain/config/settings.py` or terminate the process occupying the port.
