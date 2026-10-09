---
title: "Security Best Practices"
description: "Security recommendations: MSP/Identity, key management, API key, sanitization, secure logging, CORS/HSTS, rate limit."
icon: material/shield-star
---

# Security best practices

## Deployment

Production requires API-key authentication and a provisioned key map. Give each client the scopes needed by its routes. Terminate HTTPS at the enterprise reverse proxy, configure `Strict-Transport-Security` there, and restrict CORS to the intended frontends. HieraChain's HSTS settings do not add the header.

Use API payload/rate limits and ordering event-pool/RAM limits for application resource protection. Configure proxy limits as well. There is no `ResourceGuardMiddleware` or `security/resource_guard.py` in the package.

## Keys and logs

Keep the complete node identity, trusted block key map and IPFS encryption key in recoverable, access-controlled storage. Rotation requires updating the approved public key maps used by verifiers. See [Key Backup](../workflows/key-backup.md) for the distinction between node identity and CLI key pair files.

Use structured named fields so `SecureLogger` can redact secrets. It does not detect log deletion or modification. Audit verification uses `AuditLogger` with a separately trusted manifest. Apply retention and access controls in the deployment's logging system.

## Authentication lockout storage

* Use the SQLite or Redis brute-force backend when API authentication runs in multiple worker processes. Both backends count failures atomically across workers.
* Memory and file backends keep attempt counts in one process; run one worker with either backend. File-backed instances reload lockouts so a lockout written by another instance becomes visible on the next check.
* Shared backend errors stop authentication. Restore the backend before serving authenticated requests again.

## Implementation references

| Area | Source |
|:-----|:-------|
| Identity and keys | `hierachain/security/identity.py`, `msp.py`, `key_manager.py`, `key_provider.py`, `identity_loader.py` |
| Caller-managed ABAC | `hierachain/security/policy_engine.py` |
| API authentication | `hierachain/security/verify/api_key_verifier.py` |
| Structured logging | `hierachain/security/secure_logging.py`, `sanitization.py` |
| API limits | `hierachain/api/middleware.py` |

## Configuration

Use `HRC_AUTH_ENABLED`, `HRC_API_KEYS_FILE`, `HRC_API_KEY_LOCATION` and `HRC_API_KEY_NAME` for API authentication. CORS uses `HRC_CORS_ALLOW_ALL` and `HRC_CORS_ORIGINS`. Rate limits use `HRC_RATE_LIMIT`, `HRC_RATE_LIMIT_RPM` and `HRC_RATE_LIMIT_BACKEND`.

See [Secure deployment](../how-to/secure-deployment.md) for provisioning commands and [Config](../reference/config.md) for defaults. OAuth, LDAP, HSM and SIEM integrations belong to the host application or enterprise gateway.
