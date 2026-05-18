---
title: "How to Run Demos"
description: "How to run demo scenarios to test HieraChain's core features."
icon: material/play-circle
---

# How to Run Demos (`demo/*`)

The `demo/` directory contains sample scripts to help you quickly get familiar with the system's key features.

## 1. Core Features Demo

This script demonstrates the flow of creating Sub-chains, sending Events, and the Channel/Private Data mechanism.

```bash
# Run the basic demo
python demo/demo.py
```

**Steps performed in the demo:**

* Initialize Main Chain and Sub-Chain (`supply_chain`).
* Register organizations and users.
* Send business events.
* Create a Private Data Collection shared only between two parties.

---

## 2. BFT Consensus over ZeroMQ Demo

Demonstrates the consensus capability of 4 nodes using the BFT protocol over a ZeroMQ network.

```bash
# Run the BFT demo
python demo/demo_zmq_consensus.py
```

---

## 3. Key Backup and Recovery Demo

Shows how to use `KeyBackupManager` to protect user private keys.

```bash
# Run the backup demo
python demo/demo_key_backup.py
```

---

## 4. IPFS Integration Demo

Illustrates how to store large data/documents on IPFS with AES-256 encryption.

```bash
# Run the IPFS demo
python demo/demo_ipfs.py
```

> **Note**: Requires the IPFS daemon to be running (default on port 5001).

---

## 5. Blockchain Explorer Demo

A simple web interface for viewing blocks and events.

```bash
# Run the explorer demo
python demo/demo_explorer.py
```

Then visit [http://localhost:2661/explorer](http://localhost:2661/explorer) (requires the API server to be running).
