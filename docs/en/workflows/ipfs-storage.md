---
title: "IPFS Encrypted Storage"
description: "Offloading large business data payloads to encrypted IPFS storage, anchoring only cryptographic CIDs."
icon: material/harddisk
---

# IPFS encrypted storage

## Overview

`IPFSClient` uploads bytes or JSON to a configured Kubo daemon and returns a CID. `upload_bytes()` and `upload_json()` encrypt by default with AES-256-GCM. Direct callers can pass `encrypt=False`, which sends plaintext to IPFS. Configure the daemon and its network access separately; the client does not enforce a private swarm.

`create_ipfs_client_from_env()` requires `HRC_IPFS_ENCRYPTION_KEY` to contain exactly 64 hexadecimal characters (32 bytes). Missing or malformed keys raise `IPFSError`. Preserve this key across restarts so previously encrypted objects remain readable. A directly constructed client can generate an in-memory key when none is supplied; that key is not a persistent recovery mechanism.

## Upload and download

```mermaid
sequenceDiagram
    participant Caller as Application
    participant IC as IPFSClient
    participant AES as AESEncryption
    participant IPFS as Kubo daemon
    Caller->>IC: upload_json(data, encrypt=True, metadata=metadata)
    IC->>IC: Serialize JSON to bytes
    IC->>AES: encrypt(bytes, canonical metadata AAD)
    AES-->>IC: ciphertext, random 12-byte nonce
    IC->>IPFS: POST /api/v0/add (pin=auto_pin)
    IPFS-->>IC: CID
    IC-->>Caller: cid, size, encrypted, nonce, metadata if provided
    Note over Caller: Retain CID, nonce and metadata; protect key separately
    Caller->>IC: download_json(cid, nonce=nonce, metadata=metadata)
    IC->>IPFS: POST /api/v0/cat?arg=cid
    IPFS-->>IC: ciphertext
    IC->>AES: decrypt(ciphertext, nonce, same metadata AAD)
    AES-->>IC: Authenticated plaintext
    IC-->>Caller: Decoded JSON
```

The ciphertext includes the GCM authentication tag. The nonce is returned separately as 24 hexadecimal characters. It is public metadata, not the encryption key. When metadata was used as additional authenticated data (AAD), supply the same metadata during download; the client serializes it with `dumps_canonical_json()`.

Uploads pass `pin` to Kubo's add RPC using `auto_pin` (default `True`). `IPFSClient.pin()` is also available for explicit pinning. Retain pins and backups according to the daemon's operational policy.

## Security and integration

| Property | Implementation |
|:---------|:---------------|
| Confidentiality | AES-256-GCM when `encrypt=True` |
| Integrity | GCM tag verification with the same key, nonce and AAD |
| Nonce | Random 96-bit nonce per encryption; replay detection requires application state |
| Key configuration | Stable `HRC_IPFS_ENCRYPTION_KEY` required by the environment factory |
| Authorization | The caller enforces permissions; the client does not invoke `PolicyEngine` |

Keep the key in a secret manager. Store the CID, nonce, encryption flag and any AAD metadata needed for retrieval. Encryption does not prevent someone who can replay an old CID from requesting the same object again.

## Errors

Upload/download HTTP failures raise `IPFSError`; encryption failures propagate as `EncryptionError`. The client has no automatic three-attempt retry or Risk Alerts integration. The application decides whether to retry and how to report failures.

`IPFSClient.is_available(cid)` checks `/api/v0/files/stat` with `arg=/ipfs/<cid>` and returns `False` for unsuccessful responses or connection failures. It does not prove that the caller has the correct decryption key.

## Key classes and methods

| Operation | Method | File |
|:----------|:-------|:-----|
| JSON upload | `IPFSClient.upload_json()` | `hierachain/api/storage/ipfs_client.py` |
| Byte upload | `IPFSClient.upload_bytes()` | `hierachain/api/storage/ipfs_client.py` |
| Encryption | `AESEncryption.encrypt()` | `hierachain/api/storage/encryption.py` |
| Pin | `IPFSClient.pin()` | `hierachain/api/storage/ipfs_client.py` |
| JSON download | `IPFSClient.download_json()` | `hierachain/api/storage/ipfs_client.py` |
| Environment factory | `create_ipfs_client_from_env()` | `hierachain/api/storage/ipfs_client.py` |

## Related

- [Policy Enforcement](./policy-enforcement.md): caller-managed authorization
- [Risk Analysis & Alerts](./risk-alerts.md): application-managed failure reporting
- [Key Backup](./key-backup.md): operator-managed key storage
