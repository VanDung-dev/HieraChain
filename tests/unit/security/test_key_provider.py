"""
Unit tests for key provider implementations.

Tests both LocalKeyProvider and FileVaultProvider functionality
including key generation, signing, verification, and vault management.
"""

import pytest
import os
from hierachain.security import (
    LocalKeyProvider, FileVaultProvider, CryptoError,
    KeyPair, verify_signature
)

def test_local_key_provider():
    # Setup
    kp = KeyPair.generate()
    provider = LocalKeyProvider(kp)
    
    # Test Public Key
    assert provider.public_key_hex == kp.public_key
    
    # Test Signing
    msg = b"hello world"
    sig = provider.sign(msg)
    
    # Verify
    assert verify_signature(kp.public_key, msg, sig) is True

def test_file_vault_provider_creation(tmp_path):
    vault_file = tmp_path / "test.vault"
    password = "secure_password_123"
    
    # Create Vault
    provider = FileVaultProvider.create_vault(str(vault_file), password)
    
    assert os.path.exists(vault_file)
    assert provider.public_key_hex is not None
    
    # Test Signing
    msg = b"secret message"
    sig = provider.sign(msg)
    
    assert verify_signature(provider.public_key_hex, msg, sig) is True

def test_file_vault_reopen(tmp_path):
    vault_file = tmp_path / "reopen.vault"
    password = "password"
    
    # Create
    original_provider = FileVaultProvider.create_vault(str(vault_file), password)
    public_key = original_provider.public_key_hex
    
    # Reopen
    reopened_provider = FileVaultProvider(str(vault_file), password)
    assert reopened_provider.public_key_hex == public_key
    
    # Sign check
    msg = b"test"
    sig = reopened_provider.sign(msg)
    assert verify_signature(public_key, msg, sig) is True

def test_file_vault_wrong_password(tmp_path):
    vault_file = tmp_path / "wrong.vault"
    password = "right_password"
    
    FileVaultProvider.create_vault(str(vault_file), password)
    
    # Try reopen with wrong password
    with pytest.raises(CryptoError, match="Invalid vault password"):
        FileVaultProvider(str(vault_file), "wrong_password")
