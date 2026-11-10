---
title: "Encryption & Keys"
description: "Signing keys, API keys and operator-managed key storage."
icon: material/key-chain
---

# Encryption and keys

This security layer manages system secrets. That includes encryption keys, signing key pairs and node identities.

## Key manager and key providers

File: `hierachain/security/key_manager.py`, `key_provider.py`

This code creates and uses key pairs:

* Ed25519 support uses Ed25519 for fast and secure digital signatures.
* Pluggable providers support several key sources:

    * `LocalKeyProvider` keeps keys in local memory.
    * `FileVaultProvider` keeps encrypted data on disk with Fernet, using AES-128-CBC with HMAC.

* API keys are hashed with SHA-256 before they reach storage or caches (`HashedKeyStorage`, cache and permission keys). The API server's `KeyManager.revoke_key()` persists API key revocation through SQLite or a configured shared Redis backend. When no revocation store is passed, `KeyManager` uses `SQLiteRevocationStore` at `HRC_API_KEY_REVOCATIONS_DB`. Revocation checks bypass cached key permissions.

## Node identity

File: `hierachain/security/identity_loader.py`

`load_node_identity()` reads the node identity configured by `HRC_VALIDATOR_IDENTITY`. The identity contains the node ID, MSP identifier string, Ed25519 signing key pair and transport keys. Loading rejects a signing public key that does not match its private key. There is no X.509 ASN.1 and no mutual TLS; TLS is expected at the reverse proxy per architecture rules.

## Key backup and recovery

Files: `hierachain/cli/key.py`, `hierachain/security/key_provider.py` (`FileVaultProvider`)

Operators manage backups through external tooling. The available key-file mechanisms are:

* Generation runs `hrc key generate --output validator_key.json` (CLI) to create an Ed25519 pair via `Ed25519PrivateKey.generate()` and write `{private_key, public_key}` hex JSON. The new file has mode `0600` on POSIX systems; generation refuses to overwrite an existing file. The `show` and `verify` commands inspect the result.
* Encrypted vault (dev and test only) uses `FileVaultProvider` to encrypt the vault file with `PBKDF2HMAC(SHA256, 310_000 iter)` and `Fernet(AES-128-CBC+HMAC)`. Its password is passed to the provider constructor. Production HSM or KMS support requires an application-specific `KeyProvider`; no built-in master-key provider exists.
* There is no multi-location backup, no SHA-512 integrity check and no auto distribution or cleanup. Operators must copy `validator_key.json` or `.vault` with external backup tooling.

## Key scope

* Block signing loads a complete node identity through `HRC_VALIDATOR_IDENTITY`, including an Ed25519 signing pair and transport keys. The CLI file containing only `private_key` and `public_key` is a provider file, not that complete identity. Back up the identity and `HRC_BLOCK_TRUSTED_KEYS_FILE` together; see [Key Backup](../workflows/key-backup.md). `HRC_MASTER_KEY_SOURCE=env` is only a compatibility alias; other values and nonempty `HRC_MASTER_KEY_FILE` are rejected because no master-key provider is implemented.
* API keys are managed by `KeyManager` (create, revoke, permission, cached via `KeyStorage`/`KeyCacheManager`), not per-entity signing keys.
* There is no built-in hierarchy like Master to Domain to Entity. Domain isolation relies on Sub-Chain separation.

## Related

*   [Authorization & Access Control](./authorization-access-control.md)
*   [Network Security](../modules/network.md)
