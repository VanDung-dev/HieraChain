"""
Key Provider Abstraction for HieraChain.

This module defines the interface for cryptographic key operations, allowing
for different storage backends (Local Memory, File Vault, HSM, KMS) without
changing the core consensus logic.
"""

from abc import ABC, abstractmethod
from typing import Optional
import json
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from hierachain.security.security_utils import KeyPair, CryptoError

class KeyProvider(ABC):
    """
    Abstract interface for key operations.
    Implementations handle how the private key is stored and accessed.
    """
    
    @property
    @abstractmethod
    def public_key_hex(self) -> str:
        """Return the public key in hex format."""
        pass
        
    @abstractmethod
    def sign(self, data: bytes) -> str:
        """
        Sign data and return hex signature.
        
        Args:
            data: Bytes to sign.
            
        Returns:
            Hex-encoded signature.
        """
        pass

class LocalKeyProvider(KeyProvider):
    """
    Standard provider that holds the KeyPair in memory.
    Used for development and backward compatibility.
    """
    
    def __init__(self, keypair: KeyPair):
        self._keypair = keypair
        
    @property
    def public_key_hex(self) -> str:
        return self._keypair.public_key
        
    def sign(self, data: bytes) -> str:
        return self._keypair.sign(data)
        
    @classmethod
    def generate(cls) -> 'LocalKeyProvider':
        """Generate a new random key provider."""
        return cls(KeyPair.generate())


class FileVaultProvider(KeyProvider):
    """
    Provider that stores the private key in an encrypted file (Virtual HSM).
    
    The private key is only decrypted briefly during the signing operation 
    (or held in protected memory depending on implementation), relying on 
    a password/master key provided at runtime.
    """
    
    def __init__(self, vault_path: str, password: str):
        """
        Initialize the vault provider.
        
        Args:
            vault_path: Path to the .vault file.
            password: Password to unlock the vault.
        """
        self.vault_path = vault_path
        self._password = password
        self._public_key: Optional[str] = None
        
        # Verify easy access by loading public key immediately
        self._load_public_key()
        
    def _derive_key(self, salt: bytes) -> bytes:
        """Derive AES key from password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self._password.encode()))

    def _load_public_key(self):
        """Load public key from vault to verify password and cache it."""
        if not os.path.exists(self.vault_path):
            raise CryptoError(f"Vault not found: {self.vault_path}")
            
        with open(self.vault_path, "rb") as f:
            data = json.load(f)
            
        encrypted_blob = base64.b64decode(data['blob'])
        salt = base64.b64decode(data['salt'])
        
        key = self._derive_key(salt)
        f = Fernet(key)
        
        try:
            decrypted = f.decrypt(encrypted_blob)
            key_data = json.loads(decrypted)
            self._public_key = key_data['public_key']
        except Exception:
            raise CryptoError("Invalid vault password or corrupted vault")

    @property
    def public_key_hex(self) -> str:
        if not self._public_key:
            self._load_public_key()
        return self._public_key # type: ignore

    def sign(self, data: bytes) -> str:
        """
        Decrypt private key, sign, and then let GC handle the cleanup.
        """
        # 1. Load and Decrypt
        with open(self.vault_path, "rb") as f:
            vault_data = json.load(f)
            
        salt = base64.b64decode(vault_data['salt'])
        key = self._derive_key(salt)
        f = Fernet(key)
        
        decrypted = f.decrypt(base64.b64decode(vault_data['blob']))
        key_data = json.loads(decrypted)
        
        # 2. Re-construct KeyPair ephemeral
        kp = KeyPair.from_private_key(key_data['private_key'])
        
        # 3. Sign
        signature = kp.sign(data)
        
        # 4. Cleanup (Variables go out of scope)
        del kp
        del key_data
        del decrypted
        
        return signature

    @classmethod
    def create_vault(cls, vault_path: str, password: str) -> 'FileVaultProvider':
        """Create a new vault with a fresh keypair."""
        # Generate fresh keys
        kp = KeyPair.generate()
        key_data = {
            'public_key': kp.public_key,
            'private_key': kp.private_key
        }
        
        # Encrypt
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        f = Fernet(key)
        
        encrypted_blob = f.encrypt(json.dumps(key_data).encode())
        
        # Save
        data = {
            'salt': base64.b64encode(salt).decode('utf-8'),
            'blob': base64.b64encode(encrypted_blob).decode('utf-8')
        }
        
        with open(vault_path, "w") as f_out:
            json.dump(data, f_out)
            
        return cls(vault_path, password)
