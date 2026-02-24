"""
Master Key Provider for secure cryptographic key source management.

This module provides a flexible and secure mechanism for loading the master
backup encryption key from multiple sources (environment variable, file, or
auto-generation), with startup security checks and warnings.

Supports the following source priority:
1. Environment variable (HRC_MASTER_BACKUP_KEY, base64-encoded)
2. File on disk (configurable path, default: config/master_backup_key.key)
3. Auto-generate a new key (saved to file for persistence)
"""

import os
import stat
import base64
import secrets
import binascii

from hierachain.security.secure_logging import get_security_logger

logger = get_security_logger()

# Expected AES-256 key length in bytes
_MASTER_KEY_LENGTH = 32

# Default env var name for master key
_ENV_VAR_NAME = "HRC_MASTER_BACKUP_KEY"

# Default file path for master key
_DEFAULT_KEY_FILE = os.path.join("config", "master_backup_key.key")


class MasterKeyError(Exception):
    """Raised when master key initialization fails."""
    pass


def _check_project_root(abs_path: str) -> list[str]:
    """Check if file is in the project root directory."""
    project_root = os.getcwd()
    key_dir = os.path.dirname(abs_path)
    if key_dir == project_root:
        return [
            f"SECURITY WARNING: Master key file '{abs_path}' is in the "
            f"project root directory. Move it to a more secure location."
        ]
    return []


def _check_file_permissions(abs_path: str) -> list[str]:
    """Check if file permissions are too open (Unix-like systems)."""
    try:
        file_stat = os.stat(abs_path)
        file_mode = file_stat.st_mode

        # Check if group or others have read permission
        if file_mode & (stat.S_IRGRP | stat.S_IROTH):
            return [
                f"SECURITY WARNING: Master key file '{abs_path}' is readable "
                f"by group or others. Set permissions to 0600."
            ]
    except OSError:
        pass
    return []


def _check_suspicious_directories(abs_path: str) -> list[str]:
    """Check if file is in a common/public directory."""
    _suspicious_dirs = ["tmp", "temp", "public", "static", "www", "htdocs"]
    path_parts = abs_path.lower().replace("\\", "/").split("/")
    for suspicious_dir in _suspicious_dirs:
        if suspicious_dir in path_parts:
            return [
                f"SECURITY WARNING: Master key file is in a potentially "
                f"public directory ('{suspicious_dir}'). Move to a "
                f"restricted location."
            ]
    return []


def _check_production_environment() -> list[str]:
    """Recommend env var for production."""
    env = os.getenv("HRC_ENV", "dev").lower()
    if env == "product":
        return [
            "SECURITY RECOMMENDATION: In production, use environment "
            "variable or secret manager instead of file-based master key."
        ]
    return []


class MasterKeyProvider:
    """
    Provides the master encryption key from configurable sources.

    Source resolution order (configurable via 'source' parameter):
    - "env": Load from environment variable only
    - "file": Load from file only
    - "auto" (default): Try env var first, then file, then auto-generate

    Security Features:
    - Startup warnings for insecure key file locations
    - Key length validation (must be exactly 32 bytes for AES-256)
    - Logging of key source for audit trail
    - Production environment warnings when using file-based keys
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize MasterKeyProvider with configuration.

        Args:
            config: Optional configuration dictionary containing:
                - source: Key source strategy ("env", "file", "auto")
                - key_file: Path to master key file
                - env_var: Name of environment variable
                - environment: Current environment ("dev", "product", "test")
        """
        config = config or {}
        self.source = config.get("source", "auto")
        self.key_file = config.get("key_file", _DEFAULT_KEY_FILE)
        self.env_var = config.get("env_var", _ENV_VAR_NAME)
        self.environment = config.get("environment", "dev")
        self._master_key: bytes | None = None

    def get_master_key(self) -> bytes:
        """
        Resolve and return the master encryption key.

        Returns:
            bytes: 32-byte master encryption key

        Raises:
            MasterKeyError: If key cannot be loaded from any source
        """
        if self._master_key is not None:
            return self._master_key

        if self.source == "env":
            self._master_key = self._load_from_env()
        elif self.source == "file":
            self._master_key = self._load_from_file()
        else:
            # "auto" mode: try env → file → generate
            self._master_key = self._load_auto()

        return self._master_key

    def _load_auto(self) -> bytes:
        """Auto-resolve key: env var → file → generate."""
        # Try environment variable first
        key = self._try_load_from_env()
        if key is not None:
            logger.info("Master key loaded from environment variable")
            return key

        # Try file
        key = self._try_load_from_file()
        if key is not None:
            # Run security checks on the key file
            warnings = self.check_key_file_security(self.key_file)
            for warning in warnings:
                logger.warning(warning)
            logger.info(
                "Master key loaded from file",
                extra={"key_file": self.key_file}
            )
            return key

        # Auto-generate as last resort
        key = self._generate_new_key()
        logger.info("Generated new master backup encryption key")
        return key

    def _load_from_env(self) -> bytes:
        """Load master key from environment variable (required)."""
        key = self._try_load_from_env()
        if key is None:
            raise MasterKeyError(
                f"Master key environment variable '{self.env_var}' is not set "
                f"or contains invalid data. Set a base64-encoded 32-byte key."
            )
        logger.info("Master key loaded from environment variable")
        return key

    def _try_load_from_env(self) -> bytes | None:
        """
        Attempt to load master key from environment variable.

        Returns:
            bytes or None: 32-byte key if valid, None otherwise
        """
        env_value = os.environ.get(self.env_var)
        if not env_value:
            return None

        try:
            key = base64.b64decode(env_value)
        except (ValueError, binascii.Error):
            logger.warning(
                f"Environment variable '{self.env_var}' contains invalid "
                f"base64 data, skipping"
            )
            return None

        if len(key) != _MASTER_KEY_LENGTH:
            logger.warning(
                f"Environment variable '{self.env_var}' contains key of "
                f"invalid length ({len(key)} bytes, expected {_MASTER_KEY_LENGTH})"
            )
            return None

        return key

    def _load_from_file(self) -> bytes:
        """Load master key from file (required)."""
        key = self._try_load_from_file()
        if key is None:
            raise MasterKeyError(
                f"Master key file '{self.key_file}' not found or contains "
                f"invalid key data."
            )

        # Run security checks
        warnings = self.check_key_file_security(self.key_file)
        for warning in warnings:
            logger.warning(warning)

        logger.info(
            "Master key loaded from file",
            extra={"key_file": self.key_file}
        )
        return key

    def _try_load_from_file(self) -> bytes | None:
        """
        Attempt to load master key from file.

        Handles both raw binary keys and legacy base64-encoded Fernet keys.

        Returns:
            bytes or None: 32-byte key if valid, None otherwise
        """
        if not os.path.exists(self.key_file):
            return None

        try:
            with open(self.key_file, "rb") as f:
                key_data = f.read()
        except (IOError, OSError) as e:
            logger.error(f"Failed to read master key file: {e}")
            return None

        return self._decode_and_validate_key(key_data)

    def _decode_and_validate_key(self, key_data: bytes) -> bytes | None:
        """
        Decode and validate the raw key data from file.

        Args:
            key_data: Raw bytes read from key file

        Returns:
            bytes or None: 32-byte key if valid, None otherwise
        """
        # Handle legacy Fernet keys (44 bytes base64-encoded → 32 bytes decoded)
        if len(key_data) == 44:
            try:
                decoded_key = base64.urlsafe_b64decode(key_data)
                if len(decoded_key) == _MASTER_KEY_LENGTH:
                    return decoded_key
            except (ValueError, binascii.Error):
                pass

        # Raw binary key
        if len(key_data) == _MASTER_KEY_LENGTH:
            return key_data

        logger.warning(
            f"Master key file '{self.key_file}' contains key of unexpected "
            f"length ({len(key_data)} bytes, expected {_MASTER_KEY_LENGTH})"
        )
        return None

    def _generate_new_key(self) -> bytes:
        """
        Generate a new master key and save it to the configured file path.

        Returns:
            bytes: Newly generated 32-byte key
        """
        key = secrets.token_bytes(_MASTER_KEY_LENGTH)

        # Ensure directory exists
        key_dir = os.path.dirname(self.key_file)
        if key_dir:
            os.makedirs(key_dir, exist_ok=True)

        # Write key to file
        with open(self.key_file, "wb") as f:
            f.write(key)

        # Attempt to restrict file permissions (limited effect on Windows)
        try:
            os.chmod(self.key_file, 0o600)
        except OSError as e:
            logger.debug(f"Could not set file permissions on {self.key_file}: {e}")

        # Warn about file-based key in production
        if self.environment == "product":
            logger.warning(
                "SECURITY WARNING: Master key stored as file in production. "
                "Consider using environment variable or a secret manager/KMS "
                f"(set {self.env_var} with base64-encoded 32-byte key)."
            )

        return key

    @staticmethod
    def check_key_file_security(key_file: str) -> list[str]:
        """
        Check the security posture of the master key file location.

        Args:
            key_file: Path to the master key file

        Returns:
            list[str]: List of security warning messages (empty if all checks pass)
        """
        warnings: list[str] = []

        if not os.path.exists(key_file):
            return warnings

        abs_path = os.path.abspath(key_file)

        # Run individual security checks
        warnings.extend(_check_project_root(abs_path))
        warnings.extend(_check_file_permissions(abs_path))
        warnings.extend(_check_suspicious_directories(abs_path))
        warnings.extend(_check_production_environment())

        return warnings
