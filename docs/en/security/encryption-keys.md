---
title: "Encryption & Keys"
description: "Signing keys, API keys, internal MSP certificates and operator-managed key storage."
icon: material/key-chain
---

# Encryption and keys

This security layer manages system secrets. That includes encryption keys, signing key pairs and identity certificates.

## Key manager and key providers

File: `hierachain/security/key_manager.py`, `key_provider.py`

This code creates and uses key pairs:

* Ed25519 support uses Ed25519 for fast and secure digital signatures.
* Pluggable providers support several key sources:

    * `LocalKeyProvider` keeps keys in local memory.
    * `FileVaultProvider` keeps encrypted data on disk with Fernet, using AES-128-CBC with HMAC.

* The API server's `KeyManager.revoke_key()` persists API key revocation through SQLite or a configured shared Redis backend. Revocation checks bypass cached key permissions.

## Certificate and identity (MSP)

File: `hierachain/security/msp.py` (`Certificate`, `CertificateAuthority`, `HierarchicalMSP`)

This code manages lightweight internal identities, not X.509:

* Internal certificate is the `Certificate` dataclass with `cert_id`, `subject`, `public_key`, `signature` (Ed25519 via `_sign_certificate`) and `is_valid()` time check. There is no X.509 ASN.1 and no mTLS.
* CA operations are `CertificateAuthority.issue_certificate()`, `revoke_certificate()` and `verify_certificate()` with an in-memory `issued_certificates` dictionary and `revoked_certificates` set. `HierarchicalMSP` uses this for org and entity registration.
* Limitation: MSP certificate revocation lives only in memory. There is no CRL distribution, no X.509 chain validation and no mutual TLS between components. TLS is expected at the reverse proxy per architecture rules.

## Key backup and recovery

Files: `hierachain/cli/key.py`, `hierachain/security/key_provider.py` (`FileVaultProvider`)

Operators manage backups through external tooling. The available key-file mechanisms are:

* Generation runs `hrc key generate --output validator_key.json` (CLI) to create an Ed25519 pair via `Ed25519PrivateKey.generate()` and write `{private_key, public_key}` hex JSON. The new file has mode `0600` on POSIX systems; generation refuses to overwrite an existing file. The `show` and `verify` commands inspect the result.
* Encrypted vault (dev and test only) uses `FileVaultProvider` to encrypt the vault file with `PBKDF2HMAC(SHA256, 310_000 iter)` and `Fernet(AES-128-CBC+HMAC)`. Its password is passed to the provider constructor. Production HSM or KMS support requires an application-specific `KeyProvider`; no built-in master-key provider exists. `HRC_VAULT_TOKEN` and `HRC_VAULT_PATH` configure the separate `SecretManager` Vault backend.
* There is no multi-location backup, no SHA-512 integrity check and no auto distribution or cleanup. Operators must copy `validator_key.json` or `.vault` with external backup tooling.

## Key scope

* Block signing loads a complete node identity through `HRC_VALIDATOR_IDENTITY`, including an Ed25519 signing pair and transport keys. The CLI file containing only `private_key` and `public_key` is a provider file, not that complete identity. Back up the identity and `HRC_BLOCK_TRUSTED_KEYS_FILE` together; see [Key Backup](../workflows/key-backup.md). `HRC_MASTER_KEY_SOURCE=env` is only a compatibility alias; other values and nonempty `HRC_MASTER_KEY_FILE` are rejected because no master-key provider is implemented.
* API keys are managed by `KeyManager` (create, revoke, permission, cached via `KeyStorage`/`KeyCacheManager`), not per-entity signing keys.
* There is no built-in hierarchy like Master to Domain to Entity. Domain isolation relies on Sub-Chain separation and MSP roles.

## Certificate initialization flow

```mermaid
graph LR
    A[Generate Ed25519 Key Pair<br/>cli/key.py] --> B[HierarchicalMSP.register_entity<br/>msp.py]
    B --> C[CA.issue_certificate<br/>Ed25519 sign]
    C --> D[Store in issued_certificates]
    D --> E[verify_certificate / revoke_certificate]
```

## Related

*   [Authorization & Access Control](./authorization-access-control.md)
*   [Network Security](../modules/network.md)
