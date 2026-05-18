---
title: "Security Module"
description: "Overview of the multi-layer security system: MSP, Policy Engine, Key Management and ZK Proofs."
icon: material/shield-lock
---

# Security Module (`hierachain/security/*`)

## Overview

The **Security** module provides enterprise-grade security capabilities for HieraChain. Instead of relying on a single protection layer, HieraChain implements a **Defense-in-Depth** strategy, spanning identity authentication, access control, resource protection, and advanced technologies such as Zero-Knowledge Proofs.

---

## 6 Main Security Pillars

The security architecture consists of 6 main threads that work closely together:

<div class="grid cards" markdown>

*   :material-account-lock:{ .lg .middle } __Authorization & Access__

    ---

    Identity management (MSP), API Key authentication, and attribute-based access control (ABAC).
    [:octicons-arrow-right-24: Details](../security/authorization-access-control.md)

*   :material-lock-alert:{ .lg .middle } __Lockdown & Logging__

    ---

    Emergency cluster lockdown mechanism and tamper-proof secure logging system.
    [:octicons-arrow-right-24: Details](../security/lockdown-logging.md)

*   :material-shield-check:{ .lg .middle } __Integrity & Guard__

    ---

    Resource protection against DoS and integrity checks of source code/configuration at startup.
    [:octicons-arrow-right-24: Details](../security/fault-tolerance-integrity.md)

*   :material-security-network:{ .lg .middle } __Risk & Sanitization__

    ---

    Anomaly detection and input data sanitization against injection attacks.
    [:octicons-arrow-right-24: Details](../security/risk-analyzer.md)

*   :material-key-chain:{ .lg .middle } __Encryption & Keys__

    ---

    Management of encryption key lifecycle (Ed25519, AES-GCM) and enterprise-standard digital certificates (X.509).
    [:octicons-arrow-right-24: Details](../security/encryption-keys.md)

*   :material-brain:{ .lg .middle } __Zero-Knowledge Proofs__

    ---

    Cross-chain private data security using zero-disclosure proof technology (ZKP).
    [:octicons-arrow-right-24: Details](../security/decentralized-zkp.md)

</div>

---

## System Integration

Every component of HieraChain is protected by these security layers:

*   **API Server**: Uses `ResourceGuard` and `APIKeyVerifier` as the first line of defense middleware.
*   **Consensus**: All consensus messages are digitally signed and integrity-checked.
*   **Storage**: Sensitive data is encrypted before storage and sanitized during queries.

---

## Security Configuration

Key settings are centrally managed in `hierachain/config/settings.py`:

*   `AUTH_ENABLED`: Enable/disable API authentication.
*   `HRC_CLUSTER_SECRET`: Secret key for cluster control commands.
*   `HRC_ENABLE_ZK_PROOFS`: Enable ZK proof verification.

---

## Related

*   [Security Architecture](../architecture/security.md)
*   [P2P Network Security](./network.md)
*   [Monitoring and Alerts](./monitoring.md)
