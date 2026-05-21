---
title: "Adapters Module"
description: "Storage/database adapters: SQLite, File (Parquet/Arrow), Redis — Flexible IO integration following the Adapter Pattern."
icon: material/vector-polyline
---

# Adapters Module (`hierachain/adapters/*`)

## 1. Overview

The **Adapters** module serves as the Abstraction Layer for data storage in HieraChain. Instead of binding business logic to a specific database type, HieraChain uses the **Adapter Pattern** to allow switching storage backends flexibly without modifying core source code.

### Main Roles

* **IO Standardization**: Provides a unified interface for storing blocks, events, metadata, and proofs.
* **Deployment Flexibility**: Supports environments from development (SQLite/File) to high-performance production (Redis/Parquet).
* **Query Optimization**: Each adapter is designed to optimize for a specific query type (e.g., File adapter optimizes for large-scale entity tracing).

---

## 2. Available Adapters

HieraChain provides three main adapters, divided into two groups: `database` and `storage`.

### 2.1 SQLite Database Adapter (`adapters/database/sqlite_adapter.py`)

Uses SQLite as the backend for systems requiring relational data integrity and flexible SQL queries.

* **Technology**: SQLite3.
* **Schema Structure**:

    * `chains`: Stores chain identity and type (Main/Sub).
    * `blocks`: Stores block headers, hashes, and metadata.
    * `events`: Stores business event details in JSON format.
    * `proofs`: Tracks cross-chain proofs between Sub-Chain and Main Chain.

* **Advantages**: ACID support, good entity relationship management, easy backup (single file).
* **Optimization**: Indexes on `entity_id`, `event_type`, and `timestamp`.

### 2.2 File Storage Adapter (`adapters/storage/file_storage.py`)

High-performance adapter for big data, using specialized file formats for analytics.

* **Technology**: **Apache Parquet** and **PyArrow**.
* **Storage Structure**:

    * `blocks/`: Stores blocks as compressed `.parquet` files (Zstd). Each block is an Arrow table.
    * `events/`: Maintains an Event Index for extremely fast tracing.
    * `chains/`: Stores chain metadata as JSON.

* **Advantages**: Very fast read/write speed, good data compression, supports **Column Pruning** (reading only required columns).
* **Special Features**:

    * `BatchBlockWriter`: Buffers data for batch writing, reducing I/O overhead.
    * `get_entity_events_optimized`: Uses Arrow Dataset to scan data across multiple block files simultaneously.

### 2.3 Redis Storage Adapter (`adapters/storage/redis_storage.py`)

Suitable for nodes requiring real-time response and hot data access.

* **Technology**: Redis (In-memory data structure).
* **Data Structures**:

    * **Hashes**: Stores blocks and metadata.
    * **Sorted Sets (ZSET)**: Stores block index by index and entity events by timestamp.
    * **Sets**: Manages lists of unique chains and entities.

* **Advantages**: Extremely low latency, supports real-time statistics.
* **Usage**: Typically used as cache or primary database for high-frequency transaction nodes.

---

## 3. Adapter Comparison

| Feature | SQLiteAdapter | FileStorageAdapter | RedisStorageAdapter |
| :--- | :--- | :--- | :--- |
| **Storage Type** | Relational database | File system (Parquet) | In-memory |
| **Best suited for** | ERP Integration, Audit | Big Data, Trace Analytics | Real-time Dashboard, High-speed Node |
| **Write Speed** | Medium | Very fast (with Batch) | Extremely fast |
| **Query Speed** | Fast (SQL) | Extremely fast (Analytical) | Fastest (Point lookup) |
| **Persistence** | High (ACID) | High (File-based) | Depends on Redis RDB/AOF config |
| **Dependencies** | None (Built-in Python) | `pyarrow` | `redis-py` |

---

## 4. Usage Guide

### Configuration via Settings

You can select the default adapter through environment variables or config file:

```bash
# Select storage backend
export HRC_STORAGE_BACKEND=sqlite  # Or "redis", "file"
export DATABASE_URL="sqlite:///my_ledger.db"
```

### Usage in Code

#### Using SQLite

```python
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter

adapter = SQLiteAdapter("data/ledger.db")
# Get chain statistics
stats = adapter.get_chain_statistics("supply_chain_v1")
print(f"Total blocks: {stats['total_blocks']}")
```

#### Using File (Parquet)

```python
from hierachain.adapters.storage.file_storage import FileStorageAdapter, BatchBlockWriter

storage = FileStorageAdapter(storage_path="./blockchain_data")

# Batch write blocks for performance optimization
with BatchBlockWriter(storage, "main_chain", batch_size=100) as writer:
    for block in new_blocks:
        writer.add(block)
```

---

## 5. Security & Data Safety

### Path Traversal Protection (CWE-22)

All adapters strictly validate chain names and paths:

* Only allow alphanumeric characters, underscores `_`, and hyphens `-`.
* Prevent navigation characters like `..` to ensure data is not written outside the specified directory.

### Secure Logging

Logging in adapters is done via `SecureLogger`, ensuring no sensitive business information is leaked in system log files.

---

## 6. Error Handling & Maintenance

* **Cleanup**: All three adapters support the `cleanup_old_data(days_to_keep)` method to automatically purge old blocks or unnecessary logs according to enterprise retention policy.
* **Data Integrity**: When using `FileStorageAdapter`, the block hash is stored directly in the Parquet file metadata, allowing integrity verification immediately upon file load without reading the entire content.

---

## Related

* [Core Concepts - Blockchain](../architecture/overview.md)
* [Storage Module](./storage.md)
* [Security Overview](./security.md)
