---
title: "How to Run Demos"
description: "How to run demo scenarios to test HieraChain's core features."
icon: material/play-circle
---

# How to Run Demos (`demo/*`)

The `demo/` directory contains library and UI demonstrations. Activate the repository environment and provision the signing identity/trusted key map from [Quickstart](../getting-started/quickstart.md) before scripts that create chains. Demo output and mocks are not production persistence or security guarantees.

## 1. Core Features Demo

This script demonstrates the flow of creating Sub-chains, sending Events, and the Channel/Private Data mechanism.

```bash
# Run the basic demo
python demo/demo.py
```

Steps performed in the demo:

* Initialize Main Chain and Sub-Chain (`supply_chain`).
* Register organizations and users.
* Send business events.
* Create a Private Data Collection shared only between two parties.

## 2. BFT Consensus over ZeroMQ Demo

Demonstrates the consensus capability of 4 nodes using the BFT protocol over a ZeroMQ network.

```bash
# Run the BFT demo
python demo/demo_zmq_consensus.py
```

## 3. Key backup and recovery

Follow [Key Backup](../workflows/key-backup.md) for CLI key files, complete node identities and encrypted development vaults. The repository has no `demo_key_backup.py` or `KeyBackupManager`.

## 4. IPFS Integration Demo

Illustrates how to store large data/documents on IPFS with AES-256 encryption.

```bash
# Run the IPFS demo
python demo/demo_ipfs.py
```

The script tries the local IPFS daemon on port 5001 and can fall back to an in-memory mock. Mock CIDs do not prove encrypted persistence or retrieval from a real daemon.

## 5. Blockchain Explorer Demo

A simple web interface for viewing blocks and events.

```bash
# Run the explorer demo
python demo/demo_explorer.py
```

The demo serves generated JSON and its dashboard separately at [http://127.0.0.1:8000/explorer](http://127.0.0.1:8000/explorer). Run `demo/demo.py` first to generate the data. This server is separate from the ledger API on port 2661.
