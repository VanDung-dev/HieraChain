---
title: "Security Architecture"
description: "Overview of architectural security mechanisms: MSP/Identity, Key/Cert, Policy, API Key, Resource Guard, CORS/HSTS/Rate Limit."
icon: material/shield-lock
---

# Security Architecture

This page describes the security mechanisms at the architectural level and how they integrate into HieraChain. The system follows strict enterprise security strategy: a multi-layered defense architecture spanning the entire application lifecycle.

## Main Security Pillars

The defense architecture consists of 6 main coordinated streams:

* **Authorization & Access Control**: 

    * `hierachain/security/{msp.py, identity.py}`: manages Organization, User, Role, and PKI Identity.
    * `hierachain/security/policy_engine.py`: permission control (ABAC).
    * `hierachain/security/verify/api_key_verifier.py`: API key authentication.

* **Lockdown & Logging**: 

    * `hierachain/security/secure_logging.py`: Tamper-evident log, PII data masking.
    * `hierachain/cluster/lockdown_protocol.py`: Emergency Lockdown with Quorum (contains `ClusterLockdownManager`).

* **Fault-tolerance & Integrity**: 

    * `hierachain/security/resource_guard.py`: Steel shield against DoS/DDoS under high load.
    * `hierachain/security/integrity.py`: Signature checksum scanning of startup files.

* **Risk Analyzer**: 

    * `hierachain/risk_management/risk_analyzer.py`: Z-score anomaly indicator tracking.
    * `hierachain/security/sanitization.py`: Input injection prevention.

* **Encryption & Keys**: 

    * `hierachain/security/{key_manager.py, key_provider.py, key_backup_manager.py, certificate.py}`: AES-GCM, Ed25519 and X.509 lifecycle for mTLS.

* **Decentralized Zero-Knowledge Proofs**:

    * `hierachain/security/zk_prover.py` & `hierachain/security/verify/zk_verifier.py`: Zero-Knowledge proof implementation for anonymous Sub-Chain data verification.

System security configuration is flexibly toggled at `hierachain/config/settings.py` (AUTH, CORS, HSTS, rate limit…).

## System Integration

* API Server (`hierachain/api/server.py`): inserts middleware (e.g. `ResourceGuardMiddleware`) and API key authentication if `AUTH_ENABLED=true`.
* Sub-Chain/Main Chain: all state-changing operations must pass authentication (when AUTH is enabled) and are logged for audit.
* Secure logging: `security/secure_logging.py`, `security/sanitization.py` reduce sensitive data leakage.

## Related Configuration (excerpt)

Variables in `settings.py`:

* `AUTH_ENABLED`, `API_KEY_LOCATION`, `API_KEY_NAME`
* `CORS_ALLOW_ALL`, `CORS_ORIGINS`
* `HSTS_ENABLED`, `HSTS_MAX_AGE`
* `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS_PER_MINUTE`

## Typical Flow

```mermaid
sequenceDiagram
    participant Client
    participant Server as API Server
    participant Guard as Resource Guard
    participant Auth as API Key Verifier
    participant Policy as Policy Engine
    participant Logic as Business Logic
    participant Audit as Audit Log

    Client->>Server: Send Request (with API Key)
    Server->>Guard: Check Resources (CPU/RAM)
    alt Resource Overloaded
        Guard-->>Server: Deny (503)
        Server-->>Client: 503 Service Unavailable
    else Resources OK
        Server->>Auth: Authenticate API Key
        alt Invalid Key
            Auth-->>Server: Deny (401)
            Server-->>Client: 401 Unauthorized
        else Valid Key
            Server->>Policy: Check Permissions (Role/Policy)
            alt Insufficient Permissions
                Policy-->>Server: Deny (403)
                Server-->>Client: 403 Forbidden
            else Sufficient Permissions
                Server->>Logic: Execute Business Logic
                Logic-->>Server: Result
                Server->>Audit: Log Access
                Server-->>Client: Return Result (200/201)
            end
        end
    end
```

1. Request to API → (optional) ResourceGuard checks CPU/RAM → API key authentication → policy/role check → execute → audit log.
2. Signature/ZK handling: events/transactions with signatures/ZK are verified by `verify/*` before acceptance.

## Related

* Security Module: [Security](../modules/security.md)
* Config Reference: [Config](../reference/config.md)
* API Ledger: [API Ledger](../reference/api-ledger.md)
