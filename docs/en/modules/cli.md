---
title: "CLI Module"
description: "Guide to using the hrc command-line tool for managing chains, events, nodes, and security in HieraChain."
icon: material/console
---

# CLI Module (`hierachain/cli/*`)

## Overview

The **CLI** module provides a powerful command-line tool named `hrc`, enabling operators and developers to interact quickly with the HieraChain system without using the web interface or making manual API calls.

The tool is built on the **Click** library, supporting logical command grouping, tab-completion, and strict parameter handling.

### Installation & Launch

When HieraChain is installed in development mode (`pip install -e .`), the `hrc` command is registered in the system. You can verify by:

```bash
hrc --help
```

---

## Main Command Groups

HieraChain's CLI system is divided into separate functional groups:

### `chain` Commands (Chain Management)

Used to initialize and monitor the hierarchical structure of chains.

*   **`hrc chain create`**: Create a new Sub-Chain.

    *   *Arguments*: `[supply_chain|healthcare|finance|manufacturing]`
    *   *Options*: `--name` (Required), `--parent` (Default: `main`).

*   **`hrc chain list`**: List all existing chains and their block counts.
*   **`hrc chain submit-proof`**: Submit cryptographic proof from Sub-Chain to Main Chain for cross-chain validation.

### `event` Commands (Event Management)

Used to record and query business activities.

*   **`hrc event add`**: Add an event to a chain.

    *   *Arguments*: `<chain_name>`, `[start_operation|complete_operation|quality_check|status_change]`
    *   *Options*: `--entity-id` (Required), `--details` (JSON string describing event details).

*   **`hrc event show`**: Display event history in a chain.

    *   *Options*: `--entity-id` (Filter by specific entity).

### `key` Commands (Key Management)

Used to generate and verify Ed25519 key pairs for Validators.

*   **`hrc key generate`**: Generate a new key pair.

    *   *Options*: `--output` (Default: `validator_key.json`), `--format` (json/hex).

*   **`hrc key show`**: Display key information from a file (masks the secret key).
*   **`hrc key verify`**: Verify the validity of a key pair (public key matches secret key).

### `node` Commands (Node Management)

Used to operate API nodes.

*   **`hrc node start`**: Start the FastAPI server.

    *   *Options*: `--host`, `--port`, `--reload` (For development).

*   **`hrc node init`**: Initialize data directory and default configuration for a new node.

### `verify` Commands (Verification)

Tools for auditors to check ledger integrity.

*   **`hrc verify chain`**: Verify the link structure between blocks (hash chaining).
*   **`hrc verify signatures`**: Verify all digital signatures of blocks and events in the database.

    *   *Options*: `--limit` (Check only the N most recent blocks), `--db` (Database path).

---

## Practical Usage Examples

### 1. Initialize the System and Create a Supply Chain

```bash
# Initialize node data
hrc node init --data-dir ./my_data

# Create a component supply chain
hrc chain create supply_chain --name logistics_01 --parent main
```

### 2. Record a Production Process

```bash
# Start production of entity ITEM-99
hrc event add logistics_01 start_operation --entity-id ITEM-99 --details '{"line": "A1"}'

# Complete and submit proof to Main Chain
hrc chain submit-proof logistics_01
```

### 3. Verify Data Integrity

```bash
# Check the 100 most recent blocks for tampering
hrc verify signatures --limit 100
```

---

## Configuration & Environment Variables

CLI reads configuration from the `chains.json` file by default, or from a file specified via a global option:

```bash
hrc --config custom_config.json chain list
```

---

## Design Principles (Developer Notes)

1.  **Atomicity**: Each CLI command must perform a single task and return the appropriate Exit Code (0: Success, >0: Failure).
2.  **Security**: Never print the full secret key to the screen. Use masking when displaying sensitive information.
3.  **Scripting Compatibility**: Output from `list` or `show` commands is formatted for easy processing with `grep`, `awk`, or `jq`.

---

## Related

*   [API Documentation](./api.md)
*   [Storage Adapters](./adapters.md)
*   [Security & Verify](./security.md)
