---
title: Quickstart
description: Quickly set up the environment and try HieraChain in minutes.
icon: material/lightning-bolt
---

# Quickstart

This document summarizes the minimum steps to try HieraChain.

## Quick Install

To get started as quickly as possible, install HieraChain with all dependencies (including dev) using one of two methods:

```bash
# Method 1: Using uv (recommended - fastest)
uv sync

# Method 2: Using pip
pip install -e .
```

> **Note:** For more installation details, see [Detailed Installation](install.md).

## Start API Server

After installation, you can start the server with:

```bash
python -m hierachain.api.server
```

Or use the CLI (if installed via pip):

```bash
hrc server start
```

By default, the server serves at `http://localhost:2661`. Open `http://localhost:2661/docs` to view the OpenAPI documentation and try endpoints.

## Quick Python Usage

The minimal example below demonstrates creating a `Sub-Chain`, recording an event, and submitting a proof to the `Main Chain`.

```python
from hierachain.hierarchical.hierarchy_manager import HierarchyManager

# 1. Initialize Hierarchy Manager
manager = HierarchyManager()

# 2. Create a sub-chain for a specific domain (e.g., supply chain)
manager.create_sub_chain("supply_chain", "generic")

# 3. Record a business operation (Event) into the Sub-Chain
success = manager.start_operation(
    "supply_chain", 
    "PROD-100", 
    "production_start", 
    {"location": "Factory-A", "operator": "user_01"}
)

# 4. Anchor Proof from Sub-Chain to Main Chain
proof_success = manager.submit_proof_to_main_chain("supply_chain")

print(f"Event recorded: {'Success' if success else 'Failure'}")
print(f"Proof anchored: {'Success' if proof_success else 'Failure'}")
```

## Using CLI (optional)

```bash
hrc --help
```

## Next Steps

* Learn about architecture details: [Overview](../architecture/overview.md)
* See the core module: [Core](../modules/core.md)
* See more test examples in [Testing](../dev/testing.md)
