---
title: "CLI Module"
description: "Guide to using the hrc command-line tool for managing chains, events, nodes, and security in HieraChain."
icon: material/console
---

# CLI Module (`hierachain/cli/*`)

## Overview

The **CLI** module provides the `hrc` command for managing HieraChain from a terminal.

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
    *   The current hierarchy manager attaches sub-chains to `main`; a named nested parent is rejected explicitly.

*   **`hrc chain list`**: List all existing chains and their block counts.
*   **`hrc chain submit-proof`**: Currently exits with a nonzero status. Use the authenticated REST proof endpoint backed by durable SQL storage.

### `event` Commands (Event Management)

Used to record and query business activities.

*   **`hrc event add`**: Add an event to a chain.

    *   *Arguments*: `<chain_name>`, `[start_operation|complete_operation|quality_check|status_change]`
    *   *Options*: `--entity-id` (Required), `--details` (JSON string describing event details).

*   **`hrc event show`**: Display event history in a chain.

    *   *Options*: `--entity-id` (Filter by specific entity).

### `key` Commands (Key Management)

Used to generate and verify Ed25519 key pairs for Validators.

*   **`hrc key generate`**: Generate a new key pair in a new file with mode `0600` on POSIX systems. An existing output file is never overwritten; the private key is not printed.

    *   *Options*: `--output` (Default: `validator_key.json`), `--format` (`json` or `hex`). The hex file contains the private key on the first line and the public key on the second line.

*   **`hrc key show`**: Display key information from a file (masks the secret key).
*   **`hrc key verify`**: Verify the validity of a key pair (public key matches secret key).

### `node` Commands (Node Management)

Used to operate API nodes.

*   **`hrc node start`**: Start the FastAPI server.

    *   *Options*: `--host`, `--port`, `--reload` (For development). The global `--config` option selects the node configuration loaded before startup.

*   **`hrc node init`**: Initialize data directory and default configuration for a new node.

### `verify` Commands (Verification)

Tools for auditors to check ledger integrity.

*   **`hrc verify chain`**: Verify block hashes, Merkle roots, chain links, and required block signatures against configured trusted keys. Missing blocks, an empty database, unavailable trusted keys, or invalid data return a nonzero exit status.
*   **`hrc verify signatures`**: Verify required block signatures and any signed events. Unsigned events are counted as unverified; an event with incomplete signing data or an invalid signature returns a nonzero exit status. An empty database also returns a nonzero exit status.

Both commands accept `--db` (SQLite path/URL or PostgreSQL URL; otherwise the configured database is used). `verify signatures` also accepts `--limit` to check only the N most recent blocks in each chain. Signed events need a public key in `details.public_key` or `details.sender_public_key` for verification.

These commands inspect stored blocks. Chain creation and event commands use the durable `HierarchyManager` registry and restore registered sub-chains from the configured SQLite or PostgreSQL store on each invocation. Event ordering uses each sub-chain's durable ordering journal.

---

## Practical Usage Examples

### 1. Initialize the System and Create a Supply Chain

```bash
# Initialize node data
hrc node init --data-dir ./my_data

# Create a component supply chain
hrc --config ./my_data/config.yaml chain create supply_chain --name logistics_01 --parent main
```

### 2. Record a Production Process

```bash
# Start production of entity ITEM-99
hrc --config ./my_data/config.yaml event add logistics_01 start_operation --entity-id ITEM-99 --details '{"line": "A1"}'

# Start the API with the same node configuration
hrc --config ./my_data/config.yaml node start

# Submit proofs through the authenticated REST API backed by durable SQL storage
curl -X POST -H "X-API-Key: $HRC_API_KEY" http://localhost:2661/api/ledger/chains/logistics_01/submit-proof
```

### 3. Verify Data Integrity

```bash
# Check the 100 most recent blocks for tampering
hrc verify signatures --limit 100
```

---

## Configuration & Environment Variables

CLI reads `data/config.yaml` by default, or from a file specified before the command with the global option:

```bash
hrc --config ./my_data/config.yaml chain list
```

`hrc node init` writes YAML containing `database_url` and `node_id`. The CLI also accepts a JSON object with those fields. It applies the values to chain commands and API startup. Explicit `DATABASE_URL`, `HRC_DATABASE_URL`, `HRC_NODE_ID`, or `NODE_ID` environment values take precedence. Configuration files may contain only `database_url` and `node_id`.

Sub-chain ordering journals are stored under `data/<chain-name>` relative to the current working directory. Keep that directory persistent and run the CLI from a stable working directory; a custom `--data-dir` currently relocates the hierarchy database and configuration, not those journals.

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
