---
title: "Security Module"
description: "Overview of the multi-layer security system: MSP, Policy Engine, Key Management and ZK Proofs."
icon: material/shield-lock
---

# Security Module (`hierachain/security/*`)

## Overview

The security module provides the main protections for HieraChain. It does not rely on one layer. Instead it combines identity, access control, resource protection, and zero-knowledge proofs so that a failure in one area does not expose the whole system.

---

## Six security areas

The design groups protections into six areas that work together:

<div class="grid cards" markdown>

*   :material-account-lock:{ .lg .middle } __Authorization and access__

    ---

    Identity management (MSP), API key authentication, and attribute-based access control (ABAC).
    [:octicons-arrow-right-24: Details](../security/authorization-access-control.md)

*   :material-lock-alert:{ .lg .middle } __Secure logging__

    ---

    Tamper-evident logging for security-sensitive operations.
    [:octicons-arrow-right-24: Details](../security/lockdown-logging.md)

*   :material-shield-check:{ .lg .middle } __Integrity and guard__

    ---

    Resource protection against DoS and integrity checks for code and configuration at startup.
    [:octicons-arrow-right-24: Details](../security/fault-tolerance-integrity.md)

*   :material-security-network:{ .lg .middle } __Input sanitization__

    ---

    Input validation and sanitization against injection attacks.
    [:octicons-arrow-right-24: Details](../security/risk-analyzer.md)

*   :material-key-chain:{ .lg .middle } __Encryption and keys__

    ---

    Key lifecycle management (Ed25519, AES-GCM) and X.509 certificates.
    [:octicons-arrow-right-24: Details](../security/encryption-keys.md)

*   :material-brain:{ .lg .middle } __Zero-knowledge proofs__

    ---

    Cross-chain privacy using zero-knowledge proofs (ZKP) so verifiers learn nothing beyond validity.
    [:octicons-arrow-right-24: Details](../security/decentralized-zkp.md)

</div>

---

## How it connects

Each part of HieraChain uses the same layers:

* API server uses `ResourceGuard` and `APIKeyVerifier` as middleware. They run first on every request.
* Consensus signs every consensus message and checks integrity before accepting it.
* Storage encrypts sensitive data before write and sanitizes input on queries.

---

## Security configuration

Main settings live in `hierachain/config/settings.py`:

* `AUTH_ENABLED` turns API authentication on or off.
* `HRC_ENABLE_ZK_PROOFS` enables ZK proof verification.

---

## Related

*   [Security Architecture](../architecture/security.md)
*   [P2P Network Security](./network.md)
*   [Monitoring and Alerts](./monitoring.md)
