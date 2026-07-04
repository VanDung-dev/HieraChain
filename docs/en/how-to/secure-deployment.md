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

In production, API key authentication must be enabled (per `ProductionSettings`). For dev/test environments, it can be enabled manually:

```dotenv
# .env
HRC_AUTH_ENABLED=true
HRC_API_KEY_LOCATION=header
HRC_API_KEY_NAME=X-API-Key
```

Client needs to send the header:

```bash
X-API-Key: <your-secret-key>
```

API key verification code: `hierachain/security/verify/api_key_verifier.py`.

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

## Resource Guard

Use `ResourceGuardMiddleware` middleware to reject requests when CPU/RAM exceeds thresholds:

```python
# Integration example (descriptive) in FastAPI app
from fastapi import FastAPI
from hierachain.security.resource_guard import ResourceGuardMiddleware

app = FastAPI()
app.add_middleware(
    ResourceGuardMiddleware,
    memory_threshold_percent=85.0,
    cpu_threshold_percent=85.0,
)
```

Module: `hierachain/security/resource_guard.py`. This middleware uses `monitoring/performance_monitor.py` to get metrics.

## Starting the Service

```bash
python -m hierachain.api.server
```

Default serves at `http://localhost:2661`. Set `HRC_API_HOST`/`HRC_API_PORT` if needed.

## Quick Verification

1. Missing API key (when `HRC_AUTH_ENABLED=true`) → expect 401/403:

    ```bash
    curl -i http://localhost:2661/api/ledger/health
    ```

2. With API key:

    ```bash
    curl -i -H "X-API-Key: <your-secret-key>" http://localhost:2661/api/ledger/health
    ```

3. Heavy load → ResourceGuard may return 503 (if thresholds exceeded).

## Secrets & Secure Configuration

* Do not print secrets to log/console.
* Use `python-dotenv` only in dev; production uses secrets systems (K8s Secret, Vault…).
* Check `hierachain/security/secure_logging.py` and `security/sanitization.py` to avoid sensitive data leakage.

## Production Checklist

Below is a quick checklist for deploying HieraChain in production:

### Mandatory

```bash
# Set production environment
export HRC_ENV=production

# Enable authentication
export HRC_AUTH_ENABLED=true

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
# Use external Vault
export HRC_VAULT_ADDR=https://vault.company.com

# Enable HSM for key management
export HRC_HSM_ENABLED=true
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
