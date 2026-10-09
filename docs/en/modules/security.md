---
title: "Security Module"
description: "Overview of the multi-layer security system: MSP, Policy Engine, Key Management and ZK Proofs."
icon: material/shield-lock
---

# Security Module (`hierachain/security/*`)

## Overview

The security module provides identity helpers, access-control policies, sanitization and signed ledger integrity. HTTP scope checks, organization policies and direct Python calls have different enforcement paths. The optional ZK interfaces currently provide development mocks; production ZK is unimplemented.

## Six security areas

The design groups protections into six areas that work together:

<div class="grid cards" markdown>

*   :material-account-lock:{ .lg .middle } __Authorization and access__

    ---

    Identity management (MSP), API key authentication, and attribute-based access control (ABAC).
    [:octicons-arrow-right-24: Details](../security/authorization-access-control.md)

*   :material-lock-alert:{ .lg .middle } __Secure logging__

    ---

    Structured JSON logs with sanitization and sensitive-field redaction. Audit verification uses the separate `AuditLogger` and a trusted manifest.
    [:octicons-arrow-right-24: Details](../security/lockdown-logging.md)

*   :material-shield-check:{ .lg .middle } __Integrity and guard__

    ---

    API and ordering resource limits, with signed-block verification during ledger loading and commitment.
    [:octicons-arrow-right-24: Details](../security/fault-tolerance-integrity.md)

*   :material-security-network:{ .lg .middle } __Input sanitization__

    ---

    Input validation and sanitization against injection attacks.
    [:octicons-arrow-right-24: Details](../security/risk-analyzer.md)

*   :material-key-chain:{ .lg .middle } __Encryption and keys__

    ---

    Ed25519 key providers, IPFS AES-GCM encryption and internal MSP certificates. MSP does not implement X.509 or mTLS.
    [:octicons-arrow-right-24: Details](../security/encryption-keys.md)

*   :material-brain:{ .lg .middle } __Zero-knowledge proofs__

    ---

    Development mocks for testing ZK proof flows; production proving and verification are unimplemented.
    [:octicons-arrow-right-24: Details](../security/decentralized-zkp.md)

</div>

## How it connects

The runtime applies these checks in their respective paths:

* Inspect API payload/rate limits, Redis failures, ordering event-pool/RAM limits and storage error logs. The API has no CPU/RAM `ResourceGuardMiddleware`.
* Signed blocks are checked against operator-approved creator keys; consensus-message checks depend on the selected component.
* IPFS uploads encrypt by default. SQL ledger storage does not automatically encrypt all stored event details; configure storage encryption and access controls at deployment.

## Security configuration

Main settings live in `hierachain/config/settings.py`:

* `AUTH_ENABLED` turns API authentication on or off.
* `HRC_ENABLE_ZK_PROOFS` enables the ZK verification path; it does not provide a production backend. See [ZK scope](../security/decentralized-zkp.md).

## Related

*   [Security Architecture](../architecture/security.md)
*   [P2P Network Security](./network.md)
*   [Monitoring and Alerts](./monitoring.md)

## Structured log field redaction

`sanitize_for_log()`, every `SecureLogger` level, security-event context, audit details and `log_user_action()` redact complete values identified by sensitive field names before traversing dictionaries and lists. Supported names include API keys, passwords, private keys, credentials, tokens, session IDs, authorization and prefixed secret fields, in snake_case, kebab-case or camelCase. Nested containers under a sensitive field become `***`; ordinary public keys remain visible. Existing string injection sanitization and text-pattern redaction still apply. Applications should supply secrets in named structured fields; arbitrary unnamed strings cannot reliably reveal their sensitivity.
