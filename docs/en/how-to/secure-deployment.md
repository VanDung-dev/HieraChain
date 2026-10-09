---
title: "Secure Deployment"
description: "Enable authentication, CORS/HSTS, Rate Limit, API Key, and ordering limits; production environment configuration guide for HieraChain."
icon: material/shield-check
---

# Secure deployment

Configure API-key authentication, CORS, rate limits and ordering limits in HieraChain. Terminate HTTPS and configure HSTS at the enterprise reverse proxy or API gateway. Provision a signing identity and trusted key map as described in [Quickstart](../getting-started/quickstart.md) before starting chains.

## Environment preparation

* Manage secrets via environment variables/secret manager (do not commit .env to VCS).
* Enable appropriate logging (`LOG_LEVEL=INFO` or `WARNING`).

## Enable API-key authentication

In production, API key authentication is mandatory. `HRC_AUTH_ENABLED=false`, a missing key file, or an invalid key file prevents startup. Configure:

```dotenv
# .env
HRC_AUTH_ENABLED=true
HRC_API_KEY_LOCATION=header
HRC_API_KEY_NAME=X-API-Key
HRC_API_KEYS_FILE=/absolute/path/to/api-keys.json
HRC_API_KEY_REVOCATIONS_DB=/absolute/path/to/persistent/auth-state.sqlite3
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

Store the printed key in the client's secret manager. For Docker Compose, set `HRC_API_KEYS_SOURCE_FILE` to this host file; Compose mounts it read-only at `/run/secrets/hrc_api_keys` on every node. For a direct process, set `HRC_API_KEYS_FILE` to the same absolute path. Keep `HRC_API_KEY_REVOCATIONS_DB` on persistent writable storage shared by workers on each host. To share revocations and lockouts across hosts, set the same `HRC_AUTH_STATE_REDIS_URL` on every node and enable Redis persistence. `KeyManager.revoke_key()` updates that shared state immediately; there is no administrative revocation endpoint. To change the key map, update the file and recreate every Compose node (or restart each direct process); the app does not reload the file while running.
The optional Compose `stress-test` profile also needs `HRC_API_KEY` set to one of the provisioned keys.

Client needs to send the header:

```bash
X-API-Key: <your-secret-key>
```

API key verification code: `hierachain/security/verify/api_key_verifier.py`. WebSocket clients must send the same header.

## CORS configuration

Only allow trusted origins in production:

```dotenv
# .env
HRC_CORS_ALLOW_ALL=false
HRC_CORS_ORIGINS=https://admin.example.com,https://console.example.com
```

## Configure HSTS at the HTTPS proxy

Set `Strict-Transport-Security` on HTTPS responses at the reverse proxy or API gateway. HieraChain declares the following settings, but its HTTP middleware does not use them to add that header:

```dotenv
# .env
HRC_HSTS_ENABLED=true
HRC_HSTS_MAX_AGE=31536000
```

## Enable rate limiting

Mitigate DoS at the application level:

```dotenv
# .env
HRC_RATE_LIMIT=true
HRC_RATE_LIMIT_RPM=100
```

Note: actual deployment should combine rate limiting at the reverse proxy (Nginx/Envoy/API Gateway).

## Ordering limits

No `ResourceGuardMiddleware` or `security/resource_guard.py` exists in code. Actual DoS/limit protections are: `api/middleware.py:add_rate_limit` / `add_payload_limit`, and `HRC_RAM_CRITICAL_THRESHOLD` / `HRC_EVENT_POOL_MAX_SIZE` checks in ordering/storage. Do not import a non-existent `ResourceGuardMiddleware`; combine app-level rate limiting with reverse-proxy limits.

## Starting the service

```bash
python -m hierachain
```

Default serves at `http://localhost:2661`. Set `HRC_API_HOST`/`HRC_API_PORT` if needed.

## Verification

1. Missing API key → expect 401:

    ```bash
    curl -i http://localhost:2661/api/ledger/chains
    ```

2. With API key:

    ```bash
    curl -i -H "X-API-Key: <your-secret-key>" http://localhost:2661/api/ledger/chains
    ```

3. Inspect API payload/rate limits, Redis failures, ordering event-pool/RAM limits and storage error logs. The API has no CPU/RAM `ResourceGuardMiddleware`.

## Secrets and configuration

* Do not log secrets from the running service or CI. The provisioning command prints the initial key once to the operator terminal; store it in a client secret manager.
* Use `python-dotenv` only in dev; production uses secrets systems (K8s Secret, Vault…).
* Check `hierachain/security/secure_logging.py` and `security/sanitization.py` to avoid sensitive data leakage.

## Production checklist

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

# Provisioned signing identity and trusted block keys
export HRC_VALIDATOR_IDENTITY=/absolute/path/to/identity.json
export HRC_BLOCK_TRUSTED_KEYS_FILE=/absolute/path/to/trusted-block-keys.json

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

# HSTS header must be configured at the HTTPS reverse proxy.
# This declared setting does not add the header in HieraChain.
export HRC_HSTS_ENABLED=true
```

### Optional enterprise integration

```bash
# Use external Vault (actual envs are HRC_VAULT_TOKEN / HRC_VAULT_PATH / HRC_VAULT_URL, not HRC_VAULT_ADDR)
export HRC_VAULT_TOKEN=your_token
export HRC_VAULT_PATH=/path/to/vault

# HSM is not a boolean HRC_HSM_ENABLED flag in code; use KeyProvider interface + HRC_VAULT_* / HSM integration externally
```

### Configuration check

After configuration, you can verify security settings with:

```python
from hierachain.config.settings import check_security_config

warnings = check_security_config()
for w in warnings:
    print(f"WARNING: {w}")
```

`check_security_config()` returns configuration warnings; it does not verify proxy headers or backend connectivity. Production app startup separately rejects disabled authentication or missing/invalid API-key configuration. Configure LDAP, HSM and SIEM integration in the host application or deployment.

## Related

* Security Module: [Security](../modules/security.md)
* Security Architecture: [Security (in-depth)](../architecture/security.md)
* Config Reference: [Config](../reference/config.md)
