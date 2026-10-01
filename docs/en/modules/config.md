---
title: "Config Module"
description: "System configuration management, secret management, and standardized logging format for HieraChain."
icon: material/cog
---

# Config Module (`hierachain/config/*`)

## Overview

The **Config** module manages HieraChain's operational settings, secret keys, and logging configuration for development and production.

---

## Core Components

<div class="grid cards" markdown>

*   :material-tune:{ .lg .middle } __Settings Management__

    ---

    __File__: `settings.py`

    * Environment-based configuration system (`HRC_ENV`).
    * Automatic parameter validation.
    * Configuration separated by group: Blockchain, Consensus, Storage, P2P, etc.

*   :material-key-chain:{ .lg .middle } __Secret Manager__

    ---

    __File__: `secret_manager.py`

    * Retrieves secrets independently of infrastructure.
    * Supports backends: Environment, HashiCorp Vault, AWS Secrets Manager.
    * Explicit default value handling for missing or unavailable secrets.

*   :material-format-list-bulleted-type:{ .lg .middle } __Structured Logging__

    ---

    __File__: `logging.py`

    * **Text** format for developers (colored, readable).
    * **JSON** format for Production environments (compatible with ELK, Cloud Logging).
    * Supports embedding Request ID for error tracing.

</div>

---

## Environment-based Configuration

HieraChain uses `HRC_ENV` to switch configurations and falls back to `ENV` when `HRC_ENV` is unset or blank. `HRC_ENV` takes precedence when both are set. Values are case-insensitive and ignore surrounding whitespace:

| Environment | Accepted values | Key Characteristics |
| :--- | :--- | :--- |
| **Development** | `dev`, `development` (default) | DEBUG log level, PostgreSQL storage by default, CORS allowed from everywhere. |
| **Production** | `production`, `prod`, `product` | Authentication enabled by default, HSTS, P2P Strict Trust. |
| **Testing** | `test`, `testing` | Fast configuration, small block size, Memory storage by default. |

An unknown nonblank environment value raises an error instead of selecting development.

---

## Secret Manager

This is a critical component for protecting sensitive keys such as `HRC_CLUSTER_SECRET` or `IPFS_ENCRYPTION_KEY`.

### Usage Example in Code:
```python
from hierachain.config.secret_manager import SecretManager

sm = SecretManager()
# Retrieve the configured field
cluster_key = sm.get_secret("HRC_CLUSTER_SECRET")
```

### Supported Backends:
1.  **Environment (`env`)**: Default, reads directly from environment variables.
2.  **Vault (`vault`)**: Connects to HashiCorp Vault KV v2.
3.  **AWS (`aws`)**: Reads a string field from a JSON object in AWS Secrets Manager.

`get_secret(key, default=None)` takes an environment variable name for `env`, or a field name for Vault/AWS. For AWS, `key` is never a SecretId: set `HRC_AWS_SECRET_NAME` to the secret name or ARN and optionally `HRC_AWS_REGION` (default `us-east-1`). The `SecretString` must be a JSON object whose requested field is a string; each call returns only that field, including an empty string when stored.

Missing configuration, missing fields, non-string fields, malformed JSON, `SecretBinary`, and AWS errors return `default` (or `None`). AWS does not fall back to environment variables or return the whole JSON object. Logs omit secret contents and exception messages. Existing AWS secrets stored as plain strings must be migrated to JSON objects with named string fields.

Vault falls back to environment variables when its URL or credential is missing; an unknown backend also selects `env`. Callers must invoke `SecretManager` explicitly: configuring its backend does not replace every `os.getenv()` call in the application.

---

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

---

## Configuration Validation

HieraChain validates configuration at startup to prevent potential operational errors:

*   **`validate_config()`**: Checks logical values (e.g., Port must be 1-65535, Block size > 0).
*   **`check_security_config()`**: Warns if security settings in Production are insufficient (e.g., Auth disabled or CORS-all enabled).

---

## Related

*   [Environment Variables (Reference)](../reference/config.md)
*   [Security Architecture](../architecture/security.md)
*   [Monitoring System](./monitoring.md)
