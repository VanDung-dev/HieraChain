---
title: "Secure Deployment"
description: "Enable authentication, CORS/HSTS, Rate Limit, API Key, and Resource Guard; production environment configuration guide for HieraChain."
icon: material/shield-check
---

# Secure Deployment

Configure HieraChain in production environment with basic protection measures (AUTH, CORS/HSTS, Rate Limit, API key) and resource protection (Resource Guard).

## Environment Preparation

* Manage secrets via environment variables/secret manager (do not commit .env to VCS).
* Enable appropriate logging (`LOG_LEVEL=INFO` or `WARNING`).

## Enable API Key Authentication

In production, API key authentication is mandatory. `HRC_AUTH_ENABLED=false`, a missing key file, or an invalid key file prevents startup. Configure:

```dotenv
# .env
HRC_AUTH_ENABLED=true
HRC_API_KEY_LOCATION=header
HRC_API_KEY_NAME=X-API-Key
HRC_API_KEYS_FILE=/absolute/path/to/api-keys.json
```

Generate an initial key and save its metadata outside the repository:

```bash
export HRC_API_KEYS_SOURCE_FILE="$HOME/.config/hierachain/api-keys.json"
python - <<'PY'
import json
import os
from pathlib import Path
from hierachain.security.key_manager import KeyManager

path = Path(os.environ["HRC_API_KEYS_SOURCE_FILE"])
path.parent.mkdir(parents=True, exist_ok=True)
manager = KeyManager()
api_key = manager.create_key(
    user_id="operator",
    permissions=["chains", "events", "proofs", "organizations:manage", "channels:manage"],
)
old_umask = os.umask(0o077)
try:
    path.write_text(json.dumps(manager.storage), encoding="utf-8")
finally:
    os.umask(old_umask)
path.chmod(0o600)
print(api_key)
PY
```

Store the printed key in the client's secret manager. For Docker Compose, set `HRC_API_KEYS_SOURCE_FILE` to this host file; Compose mounts it read-only at `/run/secrets/hrc_api_keys` on every node. For a direct process, set `HRC_API_KEYS_FILE` to the same absolute path. To rotate or revoke a key, update the file and recreate every Compose node (or restart each direct process); the app does not reload the file while running.
The optional Compose `stress-test` profile also needs `HRC_API_KEY` set to one of the provisioned keys.

Client needs to send the header:

```bash
X-API-Key: <your-secret-key>
```

API key verification code: `hierachain/security/verify/api_key_verifier.py`. WebSocket clients must send the same header.

## CORS Configuration

Only allow trusted origins in production:

```dotenv
# .env
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=https://admin.example.com,https://console.example.com
```

## Enable HSTS (HTTPS)

Add HSTS header to force HTTPS in browsers:

```dotenv
# .env
HRC_HSTS_ENABLED=true
HRC_HSTS_MAX_AGE=31536000
```

## Enable Rate Limiting

Mitigate DoS at the application level:

```dotenv
# .env
HRC_RATE_LIMIT=true
HRC_RATE_LIMIT_RPM=100
```

Note: actual deployment should combine rate limiting at the reverse proxy (Nginx/Envoy/API Gateway).

## Resource Guard (Note)

No `ResourceGuardMiddleware` or `security/resource_guard.py` exists in code. Actual DoS/limit protections are: `api/middleware.py:add_rate_limit` / `add_payload_limit`, and `HRC_RAM_CRITICAL_THRESHOLD` / `HRC_EVENT_POOL_MAX_SIZE` checks in ordering/storage. Do not import a non-existent `ResourceGuardMiddleware`; combine app-level rate limiting with reverse-proxy limits.

## Starting the Service

```bash
python -m hierachain.api.server
```

Default serves at `http://localhost:2661`. Set `HRC_API_HOST`/`HRC_API_PORT` if needed.

## Quick Verification

1. Missing API key → expect 401:

    ```bash
    curl -i http://localhost:2661/api/ledger/chains
    ```

2. With API key:

    ```bash
    curl -i -H "X-API-Key: <your-secret-key>" http://localhost:2661/api/ledger/chains
    ```

3. Heavy load → ResourceGuard may return 503 (if thresholds exceeded).

## Secrets & Secure Configuration

* Do not log secrets from the running service or CI. The provisioning command prints the initial key once to the operator terminal; store it in a client secret manager.
* Use `python-dotenv` only in dev; production uses secrets systems (K8s Secret, Vault…).
* Check `hierachain/security/secure_logging.py` and `security/sanitization.py` to avoid sensitive data leakage.

## Production Checklist

Below is a quick checklist for deploying HieraChain in production:

### Mandatory

```bash
# Set production environment
export HRC_ENV=production

# Configure PostgreSQL explicitly when using the PostgreSQL storage backend
export HRC_STORAGE_BACKEND=postgres
export DATABASE_URL=postgresql+psycopg://user:password@db:5432/hierachain
# HRC_DATABASE_URL may be used instead of DATABASE_URL

# Enable authentication
export HRC_AUTH_ENABLED=true
export HRC_API_KEYS_FILE=/absolute/path/to/api-keys.json

# Strict P2P trust policy
export HRC_P2P_TRUST_POLICY=strict
```

### Recommended

```bash
# Use environment variable for master key
export HRC_MASTER_KEY_SOURCE=env

# Enable rate limiting
export HRC_RATE_LIMIT=true
export HRC_RATE_LIMIT_RPM=100

# Enable HSTS
export HRC_HSTS_ENABLED=true
```

### Optional (Enterprise)

```bash
# Use external Vault (actual envs are HRC_VAULT_TOKEN / HRC_VAULT_PATH / HRC_VAULT_URL, not HRC_VAULT_ADDR)
export HRC_VAULT_TOKEN=your_token
export HRC_VAULT_PATH=/path/to/vault

# HSM is not a boolean HRC_HSM_ENABLED flag in code; use KeyProvider interface + HRC_VAULT_* / HSM integration externally
```

### Configuration Check

After configuration, you can verify security settings with:

```python
from hierachain.config.settings import check_security_config

warnings = check_security_config()
for w in warnings:
    print(f"WARNING: {w}")
```

!!! tip "Tip"
    * Only WARN, don't prevent dev from using insecure mode (keeps flexibility)
    * Devs handle enterprise integrations (LDAP, HSM, SIEM) externally

## Related

* Security Module: [Security](../modules/security.md)
* Security Architecture: [Security (in-depth)](../architecture/security.md)
* Config Reference: [Config](../reference/config.md)
