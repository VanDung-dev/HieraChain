---
title: "Security Best Practices"
description: "Security recommendations: MSP/Identity, key management, API key, sanitization, secure logging, CORS/HSTS, rate limit."
icon: material/shield-star
---

# Security Best Practices

## Purpose

Recommends standard practices for deploying HieraChain securely in production environments.

## Core Recommendations

* Enable AUTH and use API keys (or upgrade to OAuth/mTLS as needed).
* Centralized key (Ed25519) management; periodic key rotation/revocation; secure backups.
* Sanitize logs and payloads to avoid sensitive data leakage.
* Enable HSTS/CORS/Rate limit appropriate to environment and valid front-ends.
* Enable resource guard to shed load when the system is overloaded.

## Related Components

* Identity/MSP/Key: `hierachain/security/{identity.py, msp.py, key_manager.py, key_provider.py, key_backup_manager.py, certificate.py}`
* Policy/Guard: `hierachain/security/{policy_engine.py, resource_guard.py}`
* Log/Sanitize: `hierachain/security/{secure_logging.py, sanitization.py}`
* API Key: `hierachain/security/verify/api_key_verifier.py`

## Configuration

* `AUTH_ENABLED`, `API_KEY_LOCATION`, `API_KEY_NAME`
* `CORS_ALLOW_ALL`, `CORS_ORIGINS`
* `HSTS_ENABLED`, `HSTS_MAX_AGE`
* `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS_PER_MINUTE`

## Quick Checklist

* [ ] Secrets via secret manager (no hard-coding).
* [ ] CORS only allows valid origins (no `*` in production).
* [ ] Enable HSTS with appropriate `max-age`; ensure HTTPS.
* [ ] Rate limit at API gateway/app level (when needed).
* [ ] Logs contain no sensitive data; enable sanitize.
* [ ] API key revocation mechanism when exposed; full audit.
