---
title: "Key Backup & Restoration"
description: "Actual key backup/restore paths in HieraChain: CLI-generated Ed25519 keys and FileVaultProvider."
icon: material/key
---

# Key backup and restoration

## Node identity backup

Block signing requires a fixed node identity and an operator-approved trusted block key map. `HRC_VALIDATOR_IDENTITY` points to the identity JSON; `HRC_BLOCK_TRUSTED_KEYS_FILE` points to the trusted public key map. Follow [Quickstart](../getting-started/quickstart.md) to provision both files.

The identity contains `node_id`, `msp_id`, `signing_key`, `signing_public_key`, `transport_secret_key` and `transport_public_key`. Back up the complete identity and the trusted key map using external tooling with restricted access. Restore them to the configured paths before starting the node. The signing private/public keys must match, and the trusted map must contain that node's approved signing public key.

Generating a new key changes the identity's signing authority. Update the trusted maps of every affected verifier through the deployment's provisioning process; copying a new private key alone does not authorize it.

## CLI key pair files

`hierachain/cli/key.py` provides these commands through `hrc`:

```bash
hrc key generate --output validator_key.json
hrc key show --input validator_key.json
hrc key verify --input validator_key.json
```

The default JSON output contains `private_key` and `public_key` as hexadecimal strings. The file is created with mode `0600` on POSIX systems, and generation refuses to overwrite an existing file. `show` masks the private key; `verify` checks whether the public key matches the private key.

This two-field file is accepted by `LocalKeyProvider.from_file()`. It is not a complete node identity and cannot be used directly as `HRC_VALIDATOR_IDENTITY`. `python -m hierachain` starts the API server; use `hrc` for key commands.

Backup and restore of CLI key files are manual. After restoring a file, run `hrc key verify --input validator_key.json`. The CLI supplies no encryption, automatic rotation or backup distribution.

## Encrypted vault for development and tests

`FileVaultProvider` in `hierachain/security/key_provider.py` stores a key pair in a password-protected vault. It derives a Fernet key using `PBKDF2HMAC(SHA256, 310_000 iterations)`; Fernet uses AES-128-CBC and HMAC. Supply the password to the provider constructor and keep a recoverable copy in the application's secret-management system.

The provider uses password-derived encryption for a local vault file. Development and tests are its documented target, but the code has no environment gate that blocks production use; suitability depends on deployment controls and requirements. Production HSM or KMS integration requires an application-specific `KeyProvider`. The vault is a key provider, not a replacement for the complete node identity JSON.

`HRC_VAULT_TOKEN` and `HRC_VAULT_PATH` configure the separate `SecretManager` Vault backend. They do not supply the `FileVaultProvider` password. MSP certificate issuance and consensus changes do not trigger automatic backups.

## Related

- [MSP Identity](./msp-identity.md): internal certificate lifecycle
- [Encryption & Keys](../security/encryption-keys.md): providers and key scope
