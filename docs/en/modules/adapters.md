---
title: "Adapters Module"
description: "Database adapters for SQLite, PostgreSQL, and Redis in hierachain/adapters/database/."
icon: material/vector-polyline
---

# Adapters Module (`hierachain/adapters/*`)

## 1. Overview

The `adapters` module provides the persistence layer for HieraChain. The core system defines common interfaces for database operations, allowing operators to select or switch database backends without changing business logic or consensus code.

### Main roles

* Standardizes database read and write operations for chains, blocks, events, proofs, and entity state.
* Supports multiple environments, with PostgreSQL as the default and SQLite as the local fallback.
* Enforces data isolation and input sanitization across database engines.

## 2. Available database adapters

All storage adapters reside in `hierachain/adapters/database/`.

### 2.1 SQLite Database Adapter (`sqlite_adapter.py`)

The fallback adapter for environments where PostgreSQL is unavailable, and the explicit choice for lightweight single-node setups.

* Technology: SQLite3 via `sqlite3` and `hierachain/adapters/database/base/sql_base.py`.
* Schema: Initialized through `sqlite_schema.py`, creating tables for `chains`, `blocks`, `events`, `proofs`, and `chain_state`.
* Strengths: Zero external service dependencies, ACID guarantees, single-file backups.
* Indexes: Built on `entity_id`, `event_type`, `block_number`, and `timestamp`.

### 2.2 PostgreSQL Database Adapter (`postgres_adapter.py`)

The relational database adapter for multi-node and enterprise deployments.

* Technology: PostgreSQL with connection pooling.
* Schema: Initialized through `postgres_schema.py` using identical schema semantics to SQLite.
* Strengths: High concurrent write capacity, connection pooling, enterprise backup tooling.
* Query features: Partition-aware queries and index scans for high-volume audit logs.

### 2.3 Redis Database Adapter (`redis_adapter.py`)

An in-memory adapter designed for high-throughput reads and real-time entity state lookups.

* Technology: Redis via `redis-py`.
* Data structures: Hashes for block headers and event payloads, sorted sets for chronological event ordering and block index ranges, and sets for unique chain identifiers.
* Strengths: Low-latency point lookups and fast entity tracing.
* Persistence: Dependent on Redis RDB snapshots and AOF configuration.

## 3. Adapter comparison

| Feature | SQLiteAdapter | PostgreSQLAdapter | RedisAdapter |
| :--- | :--- | :--- | :--- |
| Storage type | Relational file | Relational server | In-memory key-value |
| Recommended use | Development, testing, edge nodes | Production, multi-node clusters | Low-latency state queries, caches |
| Write latency | Low | Low to medium | Very low |
| Query flexibility | Full SQL | Full SQL | Key and index lookups |
| Persistence | ACID local file | ACID enterprise server | RDB / AOF snapshot |
| External service | None | PostgreSQL 13+ | Redis 6+ |

## 4. Configuration and usage

### Configuration via settings

Set the storage backend using environment variables:

```bash
# Available backends: sqlite, postgres, redis, memory
export HRC_STORAGE_BACKEND=sqlite
export DATABASE_URL="sqlite:///data/ledger.db"

# Or for PostgreSQL
# export HRC_STORAGE_BACKEND=postgres
# export DATABASE_URL="postgresql://user:pass@localhost:5432/hierachain"
```

### Usage in code

#### Using SQLite

```python
from hierachain.adapters.database.sqlite_adapter import SQLiteAdapter

adapter = SQLiteAdapter("data/ledger.db")
stats = adapter.get_chain_statistics("supply_chain_ledger")
print(f"Total blocks: {stats['total_blocks']}")
```

#### Using PostgreSQL

```python
from hierachain.adapters.database.postgres_adapter import PostgreSQLAdapter

adapter = PostgreSQLAdapter(connection_string="postgresql://user:pass@localhost:5432/hierachain")
stats = adapter.get_chain_statistics("supply_chain_ledger")
print(f"Total blocks: {stats['total_blocks']}")
```

#### Using Redis

```python
from hierachain.adapters.database.redis_adapter import RedisAdapter

adapter = RedisAdapter(host="localhost", port=6379, db=0)
stats = adapter.get_chain_statistics("supply_chain_ledger")
print(f"Total blocks: {stats['total_blocks']}")
```

## 5. Security and validation

### Path traversal protection

Adapters validating file paths or chain names enforce strict pattern matching:

* Names allow alphanumeric characters, underscores `_`, and hyphens `-`.
* Path traversal sequences (`..`, `/`, `\`) are rejected before executing filesystem or query commands.

### Secure logging

Adapters log queries and connection events through `SecureLogger`, redacting database credentials, auth tokens, and sensitive business details.

## 6. Maintenance and retention

* Data cleanup: Relational adapters support purging historical event logs beyond retention thresholds set by `HRC_SQL_RETENTION_DAYS`.
* Logging and journals: Persistent binary journals and forensic error records use `hierachain/core/parquet_log.py` and `hierachain/error_mitigation/journal.py`, keeping chain persistence decoupled from diagnostic logging.

## Related

* [Storage Module](./storage.md)
* [Configuration Reference](../reference/config.md)
* [Security Overview](./security.md)
