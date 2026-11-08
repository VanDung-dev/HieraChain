---
title: "Config Module"
description: "System configuration management, secret management, and standardized logging format for HieraChain."
icon: material/cog
---

# Config Module (`hierachain/config/*`)

## Overview

The Config module manages HieraChain's operational settings, secret keys, and logging configuration for development and production.

## Core Components

<div class="grid cards" markdown>

*   :material-tune:{ .lg .middle } __Settings Management__

    ---

    __File__: `settings.py`

    * Environment-based configuration system (`HRC_ENV`).
    * Explicit helpers for parameter validation and security warnings.
    * Configuration separated by group: Blockchain, Consensus, Storage, P2P, etc.

*   :material-format-list-bulleted-type:{ .lg .middle } __Structured Logging__

    ---

    __File__: `logging.py`

    * Text format for developers (colored, readable).
    * JSON format for Production environments (compatible with ELK, Cloud Logging).
    * Supports embedding Request ID for error tracing.

</div>

## Environment-based Configuration

HieraChain uses `HRC_ENV` to switch configurations and falls back to `ENV` when `HRC_ENV` is unset or blank. `HRC_ENV` takes precedence when both are set. Values are case-insensitive and ignore surrounding whitespace:

| Environment | Accepted values | Key Characteristics |
| :--- | :--- | :--- |
| Development | `dev`, `development` (default) | DEBUG log level, PostgreSQL storage by default, CORS allowed from everywhere. |
| Production | `production`, `prod`, `product` | Authentication required; PostgreSQL storage by default. |
| Testing | `test`, `testing` | Fast configuration, small block size, Memory storage by default. |

An unknown nonblank environment value raises an error instead of selecting development.

The settings module loads `.env` before it defines environment-backed settings. Set `HRC_ENV_FILE` to load another dotenv file; values already present in the process environment take precedence.

## Secrets

Secrets are supplied by environment variables or by the platform's secret system (Kubernetes Secret, Vault, cloud secret manager). The package reads `HRC_MASTER_KEY_SOURCE`; only `env` is accepted. Any other source value, or a nonempty `HRC_MASTER_KEY_FILE`, raises a configuration error because the runtime has no alternate master-key provider. Remove those unsupported settings before startup.

## Standardized Logging (Observability)

You can change the log format via the `HRC_LOG_FORMAT` environment variable:

*   **For Dev (`text`)**:
    ```text
    INFO  hierachain.api.server  Starting HieraChain Node on localhost:2661...
    ```

*   **For Ops (`json`)**:
    ```json
    {"timestamp": "2024-03-20T10:00:00", "level": "INFO", "logger": "hierachain.api", "message": "Node started", "request_id": "abc-123"}
    ```

## Configuration Validation

The API and CLI startup paths perform their own validation. Startup rejects unknown environments, unsupported master-key sources and invalid production authentication or storage configuration.

## Related

*   [Environment Variables (Reference)](../reference/config.md)
*   [Security Architecture](../architecture/security.md)
*   [Network](./network.md)
