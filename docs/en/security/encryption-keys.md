---
title: "Encryption & Keys"
description: "Encryption key lifecycle management, X.509 certificates, and secure key storage."
icon: material/key-chain
---

# Encryption & Keys

This security layer manages all system "secrets", including encryption keys, signing key pairs, and identity certificates.

## 1. Key Manager & Key Providers

**File**: `hierachain/security/key_manager.py`, `key_provider.py`

Manages the creation and usage of key pairs:

*   **Ed25519 Support**: Uses the Ed25519 algorithm for high-speed and secure digital signatures.
*   **Pluggable Providers**: Supports multiple key sources:

    *   `LocalKeyProvider`: Local storage (In-memory).
    *   `FileVaultProvider`: Encrypted storage on disk using **AES-256-GCM**.

*   **API Key Lifecycle**: Manages the full API Key lifecycle from creation to revocation.

## 2. Certificate Management (X.509)

**File**: `hierachain/security/certificate.py`

Manages digital identities for nodes and services:

*   **X.509 Standards**: Complies with enterprise digital certificate standards.
*   **mTLS Support**: Provides necessary certificates for mutual TLS authentication between components.
*   **CRL (Certificate Revocation List)**: Maintains a list of revoked certificates to ensure security.

## 3. Key Backup & Recovery

**File**: `hierachain/security/key_backup_manager.py`

Ensures disaster recovery capability:

*   **Encrypted Backups**: Backs up keys in encrypted form with integrity verification via Hash.
*   **Multi-location Storage**: Supports backup at multiple locations to prevent data loss.
*   **Secure Cleanup**: Safely removes old backups to prevent leakage.

---

## Key Management Hierarchy

HieraChain uses a key hierarchy model for optimal security:

1.  **Master Key**: Root key used to encrypt other keys (typically stored in a high-security environment).
2.  **Domain Keys**: Keys used for each Sub-Chain.
3.  **Entity/User Keys**: Signing key pairs for each entity or end-user.

---

## Certificate Initialization Flow

```mermaid
graph LR
    A[Generate Ed25519 Key Pair] --> B[Create CSR - Certificate Signing Request]
    B --> C[Hierarchical MSP Review]
    C --> D[Sign with MSP Root CA]
    D --> E[Distribute X.509 Certificate]
    E --> F[Use for Secure Communication]
```

---

## Related

*   [Authorization & Access Control](./authorization-access-control.md)
*   [Network Security](../modules/network.md)
