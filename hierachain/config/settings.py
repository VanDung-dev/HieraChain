"""
Configuration settings for HieraChain Ledger

This module provides the configuration management for the HieraChain system.
It defines settings for various components including blockchain parameters, consensus
mechanisms, storage backends, security features, and integration capabilities.

The configuration supports multiple environments (development, production, testing) and
provides validation mechanisms to ensure system integrity.
"""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from hierachain.config.version import VERSION, get_version

# Environment-backed class attributes below are captured during import. Load
# the configured dotenv file first, before any Settings subclass is defined.
load_dotenv(Path(os.getenv("HRC_ENV_FILE", ".env")))


def _configured_database_url() -> str:
    """Return the first nonblank database URL explicitly set by the operator."""
    return (
        (os.getenv("DATABASE_URL") or "").strip()
        or (os.getenv("HRC_DATABASE_URL") or "").strip()
    )


def _first_nonblank_environment_value(*names: str, default: str = "") -> str:
    """Return the first nonblank configured environment value."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _environment_csv(*names: str) -> list[str]:
    """Read the first configured comma-separated environment value."""
    value = _first_nonblank_environment_value(*names)
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """Ledger configuration settings"""

    def __init__(self) -> None:
        """Reject unsupported key-source configuration instead of ignoring it."""
        source = os.getenv("HRC_MASTER_KEY_SOURCE", "").strip().lower()
        unsupported: list[str] = []
        if source and source != "env":
            unsupported.append("HRC_MASTER_KEY_SOURCE")
        if os.getenv("HRC_MASTER_KEY_FILE", "").strip():
            unsupported.append("HRC_MASTER_KEY_FILE")
        if unsupported:
            names = ", ".join(unsupported)
            raise ValueError(
                f"Unsupported master-key configuration ({names}); "
                "the runtime does not provide a master-key source"
            )
    
    # Environment - use property ENV below
    
    @property
    def env(self) -> str:
        """Auto-detect environment from environment variable."""
        env = (
            (os.getenv("HRC_ENV") or "").strip()
            or (os.getenv("ENV") or "").strip()
        ).lower()
        if env in ("production", "prod", "product"):
            return "production"
        if env in ("development", "dev"):
            return "development"
        if env in ("test", "testing"):
            return "test"
        if not env:
            return "development"
        raise ValueError(f"Unsupported HRC_ENV/ENV value: {env!r}")
    
    # Ledger version
    VERSION = get_version(VERSION)
    Ledger_NAME = "HieraChain"
    NODE_ID = _first_nonblank_environment_value(
        "HRC_NODE_ID", "NODE_ID", default="default-node"
    )

    # Consensus settings
    # MainChain Inter-Organization Consensus Type
    # Options: "proof_of_federation" (Consortium Alliance default), "proof_of_authority" (Single MainChain)
    MAINCHAIN_CONSENSUS = os.getenv(
        "HRC_MAINCHAIN_CONSENSUS",
        os.getenv("HRC_CONSENSUS_TYPE", "proof_of_authority")
    )
    # Backward compatibility alias
    CONSENSUS_TYPE = MAINCHAIN_CONSENSUS
    # PoA has no additional spacing delay unless explicitly configured.
    BLOCK_INTERVAL = float(os.getenv("HRC_BLOCK_INTERVAL", "0.0"))

    # Storage settings - memory, redis, sqlite, postgres (postgresql alias)
    @property
    def STORAGE_BACKEND(self) -> str:
        backend = (os.getenv("HRC_STORAGE_BACKEND") or "").strip().lower()
        if backend:
            if backend not in {"memory", "redis", "sqlite", "postgres", "postgresql"}:
                raise ValueError(f"Unsupported HRC_STORAGE_BACKEND value: {backend!r}")
            return backend
        db_url = _configured_database_url()
        if db_url.startswith(("sqlite://", "sqlite3://")):
            return "sqlite"
        if db_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            return "postgres"
        return self.DEFAULT_STORAGE_BACKEND

    DEFAULT_STORAGE_BACKEND = "postgres"
    
    # Hard limit for DoS protection
    EVENT_POOL_MAX_SIZE = int(os.getenv("HRC_EVENT_POOL_MAX_SIZE", "10000"))

    # Security settings
    AUTH_ENABLED = os.getenv("HRC_AUTH_ENABLED", "false").lower() == "true"
    API_KEY_LOCATION = os.getenv("HRC_API_KEY_LOCATION", "header")
    API_KEY_NAME = os.getenv("HRC_API_KEY_NAME", "X-API-Key")
    
    # Brute-force protection for API key verification
    AUTH_BRUTE_FORCE_MAX_FAILURES = int(os.getenv("HRC_BF_MAX_FAILURES", "5"))
    AUTH_BRUTE_FORCE_LOCKOUT_SECONDS = int(os.getenv("HRC_BF_LOCKOUT_SECONDS", "900"))
    AUTH_BRUTE_FORCE_WINDOW_SECONDS = int(os.getenv("HRC_BF_WINDOW_SECONDS", "300"))
    AUTH_STATE_REDIS_URL = os.getenv("HRC_AUTH_STATE_REDIS_URL", "").strip()
    API_KEY_REVOCATIONS_DB = os.getenv("HRC_API_KEY_REVOCATIONS_DB", "data/api_key_revocations.sqlite3")
    
    # Validator Identity
    VALIDATOR_IDENTITY_PATH = os.getenv("HRC_VALIDATOR_IDENTITY", "validator_key.json")
    BLOCK_TRUSTED_KEYS_FILE = os.getenv("HRC_BLOCK_TRUSTED_KEYS_FILE", "")

    # P2P Network settings
    # Enable P2P network layer
    P2P_ENABLED = os.getenv("HRC_P2P_ENABLED", "true").lower() == "true"
    # Container networking requires binding 0.0.0.0
    P2P_HOST = os.getenv("HRC_P2P_HOST", "0.0.0.0")  # nosec B104
    P2P_PORT = int(
        _first_nonblank_environment_value("HRC_P2P_PORT", "NODE_PORT", default="5555")
    )
    # Comma-separated list of seed nodes: node_id@ip:port
    P2P_PEERS: list[str] = _environment_csv("HRC_PEERS", "PEERS")

    # CORS settings (defaults allow all for development)
    CORS_ALLOW_ALL = os.getenv("HRC_CORS_ALLOW_ALL", "true").lower() == "true"
    CORS_ORIGINS: list[str] = (
        os.getenv("HRC_CORS_ORIGINS", "").split(",")
        if os.getenv("HRC_CORS_ORIGINS") else []
    )
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # Rate Limiting (disabled by default)
    RATE_LIMIT_ENABLED = os.getenv("HRC_RATE_LIMIT", "false").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("HRC_RATE_LIMIT_RPM", "100"))
    # Rate limit backend: "memory" (default, single-node) or "redis" (cluster-wide)
    RATE_LIMIT_BACKEND = os.getenv("HRC_RATE_LIMIT_BACKEND", "memory")
    
    # API settings
    API_VERSION = "ledger"
    API_HOST = os.getenv("HRC_API_HOST", "localhost")
    API_PORT = int(os.getenv("HRC_API_PORT", "2661"))
    
    # Proxy Trust settings (for HTTP/2, HTTP/3 Gateway compatibility)
    TRUSTED_PROXIES = os.getenv("HRC_TRUSTED_PROXIES", "127.0.0.1")
    
    # CLI settings
    CLI_CONFIG_FILE = "data/config.yaml"
    
    # Database settings (if using database storage)
    DATABASE_URL = _configured_database_url() or "postgresql://localhost:5432/hierachain"
    
    # Redis settings (if using Redis storage)
    REDIS_HOST = _first_nonblank_environment_value(
        "HRC_REDIS_HOST", "REDIS_HOST", default="localhost"
    )
    REDIS_PORT = int(
        _first_nonblank_environment_value("HRC_REDIS_PORT", "REDIS_PORT", default="6379")
    )
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    
    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    # Enable detailed SQL logging (query echo, verbose DB errors)
    # Should be False in production to avoid leaking DB schema details
    LOG_SQL_DETAIL = os.getenv("HRC_LOG_SQL_DETAIL", "false").lower() == "true"
    
    # IPFS Storage settings (for off-chain data storage)
    IPFS_ENABLED = os.getenv("HRC_IPFS_ENABLED", "false").lower() == "true"

    # Prometheus metrics (disabled by default, enable in production for observability)
    METRICS_ENABLED = os.getenv("HRC_METRICS_ENABLED", "false").lower() == "true"

    # Zero Knowledge Proof settings
    # Enable trustless verification of state transitions
    ENABLE_ZK_PROOFS = os.getenv("HRC_ENABLE_ZK_PROOFS", "false").lower() == "true"
    ZK_MODE = os.getenv("HRC_ZK_MODE", "mock")  # "mock" or "production"
    ZK_VERIFICATION_KEY_PATH = os.getenv("HRC_ZK_VERIFICATION_KEY", "")
    ZK_PROVING_KEY_PATH = os.getenv("HRC_ZK_PROVING_KEY", "")
    ZK_CIRCUIT_PATH = os.getenv("HRC_ZK_CIRCUIT", "")
    ZK_PROOF_REQUIRED_FOR_MAINCHAIN = (
        os.getenv("HRC_ZK_REQUIRED_MAINCHAIN", "false").lower() == "true"
    )

    # Cross-level State Sync settings
    CROSS_LEVEL_SYNC_ENABLED = (
        os.getenv("HRC_CROSS_LEVEL_SYNC", "true").lower() == "true"
    )
    CROSS_LEVEL_SYNC_BATCH_SIZE = int(os.getenv("HRC_CROSS_LEVEL_BATCH", "100"))
    CROSS_LEVEL_SYNC_TIMEOUT = float(os.getenv("HRC_CROSS_LEVEL_TIMEOUT", "30.0"))

    @classmethod
    def get_api_config(cls) -> dict[str, Any]:
        """Get API configuration"""
        return {
            "version": cls.API_VERSION,
            "host": cls.API_HOST,
            "port": cls.API_PORT,
            "trusted_proxies": cls.TRUSTED_PROXIES
        }

    @classmethod
    def get_auth_config(cls) -> dict[str, Any]:
        """Get authentication configuration"""
        lockout_backend = (
            "redis" if cls.AUTH_STATE_REDIS_URL else
            "sqlite" if cls().env == "production" else "file"
        )
        return {
            "enabled": cls.AUTH_ENABLED,
            "key_location": cls.API_KEY_LOCATION,
            "key_name": cls.API_KEY_NAME,
            "brute_force": {
                "max_failures": cls.AUTH_BRUTE_FORCE_MAX_FAILURES,
                "lockout_duration": cls.AUTH_BRUTE_FORCE_LOCKOUT_SECONDS,
                "tracking_window": cls.AUTH_BRUTE_FORCE_WINDOW_SECONDS,
                "storage_backend": lockout_backend,
                "storage_path": (
                    cls.API_KEY_REVOCATIONS_DB if lockout_backend == "sqlite" else "data/brute_force"
                ),
                "redis_url": cls.AUTH_STATE_REDIS_URL or None,
            },
        }

    @classmethod
    def get_p2p_config(cls) -> dict[str, Any]:
        """Get P2P network security configuration"""
        return {
            "enabled": cls.P2P_ENABLED,
            "host": cls.P2P_HOST,
            "port": cls.P2P_PORT,
            "seed_nodes": cls.P2P_PEERS,
        }

    @classmethod
    def get_cors_config(cls) -> dict[str, Any]:
        """
        Get CORS middleware configuration based on current settings.
        
        When CORS_ALLOW_ALL is True, uses wildcard origins with credentials
        disabled (CORS spec forbids allow_origins=['*'] with credentials).
        When CORS_ALLOW_ALL is False, uses explicit origins with credentials.
        """
        if cls.CORS_ALLOW_ALL:
            return {
                "allow_origins": ["*"],
                "allow_credentials": False,
                "allow_methods": cls.CORS_ALLOW_METHODS,
                "allow_headers": cls.CORS_ALLOW_HEADERS,
            }
        return {
            "allow_origins": cls.CORS_ORIGINS if cls.CORS_ORIGINS else [],
            "allow_credentials": True,
            "allow_methods": cls.CORS_ALLOW_METHODS,
            "allow_headers": cls.CORS_ALLOW_HEADERS,
        }

# Environment-specific settings
class DevelopmentSettings(Settings):
    """Development environment settings"""
    LOG_LEVEL = "DEBUG"
    API_HOST = os.getenv("HRC_API_HOST", "localhost")  # Allow override for Docker


class ProductionSettings(Settings):
    """Production environment settings - Security hardened by default"""
    
    # Logging - less verbose in production
    LOG_LEVEL = "WARNING"
    
    # API - default to explicit localhost, but allow 0.0.0.0 via env for containers
    API_HOST = os.getenv("HRC_API_HOST", "127.0.0.1")  # nosec
    
    # Storage - use persistent PostgreSQL storage
    DEFAULT_STORAGE_BACKEND = "postgres"
    
    # === SECURITY: Authentication is mandatory in production ===
    AUTH_ENABLED = True
    
    # === CORS: Restricted in production ===
    # Override with env var HRC_CORS_ORIGINS for specific domains
    CORS_ALLOW_ALL = False
    CORS_ORIGINS: list[str] = (
        os.getenv("HRC_CORS_ORIGINS", "").split(",")
        if os.getenv("HRC_CORS_ORIGINS") else []
    )
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = [
        "Authorization", "Content-Type", "X-API-Key", "X-Request-ID"
    ]
    
    # === Rate Limiting: Recommended ===
    RATE_LIMIT_ENABLED = os.getenv("HRC_RATE_LIMIT", "true").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("HRC_RATE_LIMIT_RPM", "100"))

    # === Logging: Restrict SQL detail in production ===
    LOG_SQL_DETAIL = False


class TestingSettings(Settings):
    """Testing environment settings"""
    LOG_LEVEL = "DEBUG"
    DEFAULT_STORAGE_BACKEND = "memory"


# Get settings based on environment
def get_settings() -> Settings:
    """Get settings based on environment variable"""
    env = Settings().env
    
    if env == "production":
        if os.getenv("HRC_AUTH_ENABLED", "true").strip().lower() != "true":
            raise ValueError("Production requires HRC_AUTH_ENABLED=true")
        return ProductionSettings()
    elif env == "test":
        return TestingSettings()
    else:
        return DevelopmentSettings()


# Global settings instance
settings = get_settings()
