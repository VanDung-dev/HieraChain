---
title: "Config Module"
description: "System configuration management, secret management, and standardized logging format for HieraChain."
icon: material/cog
---

# Config Module (`hierachain/config/*`)

## Overview

The **Config** module is the control center of HieraChain, responsible for managing hundreds of operational parameters, ensuring the security of secret keys, and providing a standardized logging mechanism for both development and production environments.

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
    * Automatic flexible fallback.

*   :material-format-list-bulleted-type:{ .lg .middle } __Structured Logging__

    ---

    __File__: `logging.py`

    * **Text** format for developers (colored, readable).
    * **JSON** format for Production environments (compatible with ELK, Cloud Logging).
    * Supports embedding Request ID for error tracing.

</div>

---

## Environment-based Configuration

HieraChain uses the `HRC_ENV` environment variable to automatically switch between optimized configurations:

| Environment | `HRC_ENV` Value | Key Characteristics |
| :--- | :--- | :--- |
| **Development** | `dev` (Default) | DEBUG log level, SQLite/Memory storage, CORS allowed from everywhere. |
| **Production** | `product` | Enforces Auth, HSTS, P2P Strict Trust, JSON log format. |
| **Testing** | `test` | Fast configuration, small block size, Memory storage by default. |

---

## Secret Manager

This is a critical component for protecting sensitive keys such as `HRC_CLUSTER_SECRET` or `IPFS_ENCRYPTION_KEY`.

### Usage Example in Code:
```python
from hierachain.config.secret_manager import SecretManager

sm = SecretManager()
# Automatically retrieves from Vault, AWS, or Env depending on configuration
cluster_key = sm.get_secret("HRC_CLUSTER_SECRET")
```

### Supported Backends:
1.  **Environment (`env`)**: Default, reads directly from environment variables.
2.  **Vault (`vault`)**: Connects to HashiCorp Vault KV v2.
3.  **AWS (`aws`)**: Connects to AWS Secrets Manager.

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
