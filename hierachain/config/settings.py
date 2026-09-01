"""
Configuration settings for HieraChain Ledger

This module provides the configuration management for the HieraChain system.
It defines settings for various components including blockchain parameters, consensus
mechanisms, storage backends, security features, and integration capabilities.

The configuration supports multiple environments (development, production, testing) and
provides validation mechanisms to ensure system integrity.
"""

import os
from typing import Any

from hierachain.config.version import get_version, VERSION


class Settings:
    """Ledger configuration settings"""
    
    # Environment - use property ENV below
    
    @property
    def env(self) -> str:
        """Auto-detect environment from environment variable."""
        env = os.getenv("HRC_ENV") or os.getenv("ENV")
        if env in ("production", "prod"):
            return "production"
        if env in ("development", "dev"):
            return "development"
        if env in ("test", "testing"):
            return "test"
        return env or "development"
    
    # Ledger version
    VERSION = get_version(VERSION)
    Ledger_NAME = "HieraChain"
    NODE_ID = os.getenv("HRC_NODE_ID", "default-node")

    # Blockchain settings
    BLOCK_SIZE_LIMIT = 1000  # Maximum events per block
    PROOF_SUBMISSION_INTERVAL = 300  # 5 minutes in seconds
    
    # Consensus settings
    # MainChain Inter-Organization Consensus Type
    # Options: "proof_of_federation" (Consortium Alliance default), "proof_of_authority" (Single MainChain)
    MAINCHAIN_CONSENSUS = os.getenv(
        "HRC_MAINCHAIN_CONSENSUS",
        os.getenv("HRC_CONSENSUS_TYPE", "proof_of_authority")
    )
    # Backward compatibility alias
    CONSENSUS_TYPE = MAINCHAIN_CONSENSUS
    BLOCK_INTERVAL = float(os.getenv("HRC_BLOCK_INTERVAL", "10.0"))
    CONSENSUS_FEDERATION_CONFIG: dict[str, Any] = {
        "min_validators": 3,
        "block_interval": 5.0
    }
    VALIDATOR_TIMEOUT = 30  # seconds
    BFT_ENABLED = True  # Enable Byzantine Fault Tolerance consensus
    BFT_FAULT_TOLERANCE = 1  # Number of Byzantine faults to tolerate (f)
    BFT_NODE_COUNT = 4  # Total number of nodes (must be >= 3f + 1)
    
    # Block Creation Mode: "event_driven" (creates block only when event arrives) or "batch_or_timer"
    BLOCK_CREATION_MODE = os.getenv("HRC_BLOCK_CREATION_MODE", "event_driven")
    BLOCK_MAX_WAIT_SEC = float(os.getenv("HRC_BLOCK_MAX_WAIT_SEC", "5.0"))

    # Parquet Partitioning & Rolling: "monthly", "daily", or "by_size_mb"
    PARQUET_ROLL_INTERVAL = os.getenv("HRC_PARQUET_ROLL_INTERVAL", "monthly")

    # PostgreSQL Sync Pipeline Mode: "realtime", "batch_worker", or "disabled"
    POSTGRES_SYNC_MODE = os.getenv("HRC_POSTGRES_SYNC_MODE", "realtime")

    # SQL hot data retention days (0 = infinite)
    SQL_RETENTION_DAYS = int(os.getenv("HRC_SQL_RETENTION_DAYS", "90"))

    # Storage settings - memory, redis, sqlite, postgres, parquet_only
    @property
    def STORAGE_BACKEND(self) -> str:
        backend = os.getenv("HRC_STORAGE_BACKEND")
        if backend:
            return backend.lower()
        db_url = os.getenv("DATABASE_URL", "")
        if db_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            return "postgres"
        return "sqlite"

    DEFAULT_STORAGE_BACKEND = os.getenv("HRC_STORAGE_BACKEND", "sqlite")
    
    # Advanced Caching settings
    ADVANCED_CACHING_ENABLED = True
    BLOCK_CACHE_SIZE = 5000
    EVENT_CACHE_SIZE = 20000
    ENTITY_CACHE_SIZE = 10000
    BLOCK_CACHE_POLICY = "lru"  # lru, lfu, fifo, ttl
    EVENT_CACHE_POLICY = "ttl"
    ENTITY_CACHE_POLICY = "lfu"
    ENTITY_TTL = 3600  # 1 hour in seconds
    
    # Hard limit for DoS protection
    EVENT_POOL_MAX_SIZE = int(os.getenv("HRC_EVENT_POOL_MAX_SIZE", "10000"))

    # Whether to synchronously sync journal to disk (fsync)
    # Recommended True for production, False for heavy stress testing on slow disks
    JOURNAL_FSYNC = os.getenv("HRC_JOURNAL_FSYNC", "true").lower() == "true"

    # % RAM usage for emergency flush (e.g., 95.0 for 95%)
    RAM_CRITICAL_THRESHOLD = float(os.getenv("HRC_RAM_CRITICAL_THRESHOLD", "95.0"))
    
    # Security settings
    IDENTITY_MANAGER_ENABLED = True
    REQUIRE_ORGANIZATION_VALIDATION = True
    AUTH_ENABLED = os.getenv("HRC_AUTH_ENABLED", "false").lower() == "true"
    API_KEY_LOCATION = os.getenv("HRC_API_KEY_LOCATION", "header")
    API_KEY_NAME = os.getenv("HRC_API_KEY_NAME", "X-API-Key")
    # Secret backend: "env" (default), "vault" (HashiCorp), "aws" (AWS Secrets Manager)
    SECRET_BACKEND = os.getenv("HRC_SECRET_BACKEND", "env")
    
    # Master key management
    # Source: "auto" (env → file → generate), "env" (env var only), "file" (file only)
    MASTER_KEY_SOURCE = os.getenv("HRC_MASTER_KEY_SOURCE", "auto")
    MASTER_KEY_FILE = os.getenv(
        "HRC_MASTER_KEY_FILE", os.path.join("config", "master_backup_key.key")
    )
    
    # Brute-force protection for API key verification
    AUTH_BRUTE_FORCE_MAX_FAILURES = int(os.getenv("HRC_BF_MAX_FAILURES", "5"))
    AUTH_BRUTE_FORCE_LOCKOUT_SECONDS = int(os.getenv("HRC_BF_LOCKOUT_SECONDS", "900"))
    AUTH_BRUTE_FORCE_WINDOW_SECONDS = int(os.getenv("HRC_BF_WINDOW_SECONDS", "300"))
    
    # Validator Identity
    VALIDATOR_IDENTITY_PATH = os.getenv("HRC_VALIDATOR_IDENTITY", "validator_key.json")

    # P2P Network settings
    # Enable P2P network layer
    P2P_ENABLED = os.getenv("HRC_P2P_ENABLED", "true").lower() == "true"
    # Container networking requires binding 0.0.0.0
    P2P_HOST = os.getenv("HRC_P2P_HOST", "0.0.0.0")  # nosec B104
    P2P_PORT = int(os.getenv("HRC_P2P_PORT", "5555"))
    # Comma-separated list of seed nodes: node_id@ip:port
    P2P_PEERS: list[str] = (
        os.getenv("HRC_PEERS", "").split(",")
        if os.getenv("HRC_PEERS")
        else []
    )
    # Trust policy: "open" (any peer unless blocked), "strict" (allowlist only)
    P2P_TRUST_POLICY = os.getenv("HRC_P2P_TRUST_POLICY", "open")
    # Comma-separated list of trusted peer IDs for strict mode
    P2P_PEER_ALLOWLIST: list[str] = (
        os.getenv("HRC_P2P_PEER_ALLOWLIST", "").split(",")
        if os.getenv("HRC_P2P_PEER_ALLOWLIST")
        else []
    )
    # Require cryptographic signature verification on P2P messages
    P2P_REQUIRE_SIGNATURES = (
        os.getenv("HRC_P2P_REQUIRE_SIGNATURES", "false").lower() == "true"
    )

    # CORS settings (defaults allow all for development)
    CORS_ALLOW_ALL = os.getenv("HRC_CORS_ALLOW_ALL", "true").lower() == "true"
    CORS_ORIGINS: list[str] = (
        os.getenv("HRC_CORS_ORIGINS", "").split(",")
        if os.getenv("HRC_CORS_ORIGINS") else []
    )
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # HTTPS/HSTS settings (disabled by default, enabled in production)
    HSTS_ENABLED = os.getenv("HRC_HSTS_ENABLED", "false").lower() == "true"
    HSTS_MAX_AGE = int(os.getenv("HRC_HSTS_MAX_AGE", "31536000"))

    # Rate Limiting (disabled by default)
    RATE_LIMIT_ENABLED = os.getenv("HRC_RATE_LIMIT", "false").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("HRC_RATE_LIMIT_RPM", "100"))
    # Rate limit backend: "memory" (default, single-node) or "redis" (cluster-wide)
    RATE_LIMIT_BACKEND = os.getenv("HRC_RATE_LIMIT_BACKEND", "memory")
    
    # Multi-Organization settings
    MULTI_ORG_ENABLED = True
    MSP_ENABLED = True  # Membership Service Provider
    ORGANIZATION_ADMIN_THRESHOLD = 1  # Minimum admins required per org
    CHANNEL_CREATION_POLICY = "majority"  # majority, unanimous, admin_only
    AFFILIATION_HIERARCHY_ENABLED = True
    
    # Integration settings
    ERP_INTEGRATION_ENABLED = True
    SUPPORTED_ERP_SYSTEMS = ["sap", "oracle", "microsoft_dynamics"]
    
    # API settings
    API_VERSION = "ledger"
    API_HOST = os.getenv("HRC_API_HOST", "localhost")
    API_PORT = int(os.getenv("HRC_API_PORT", "2661"))
    
    # Proxy Trust settings (for HTTP/2, HTTP/3 Gateway compatibility)
    TRUSTED_PROXIES = os.getenv("HRC_TRUSTED_PROXIES", "127.0.0.1")
    
    # CLI settings
    CLI_CONFIG_FILE = "chains.json"
    CLI_LOG_LEVEL = "INFO"
    
    # Database settings (if using database storage)
    DATABASE_URL = os.getenv(
        "DATABASE_URL", os.getenv("HRC_DATABASE_URL", "sqlite:///hierachain.db")
    )
    
    # Redis settings (if using Redis storage)
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    
    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # Log output format: "text" (default) or "json" (structured, production-ready)
    LOG_OUTPUT_FORMAT = os.getenv("HRC_LOG_FORMAT", "text")
    # Enable detailed SQL logging (query echo, verbose DB errors)
    # Should be False in production to avoid leaking DB schema details
    LOG_SQL_DETAIL = os.getenv("HRC_LOG_SQL_DETAIL", "false").lower() == "true"
    
    # IPFS Storage settings (for off-chain data storage)
    IPFS_ENABLED = os.getenv("HRC_IPFS_ENABLED", "false").lower() == "true"
    IPFS_HOST = os.getenv("HRC_IPFS_HOST", "/ip4/127.0.0.1/tcp/5001")
    IPFS_AUTO_PIN = os.getenv("HRC_IPFS_AUTO_PIN", "true").lower() == "true"
    IPFS_TIMEOUT = int(os.getenv("HRC_IPFS_TIMEOUT", "120"))
    IPFS_ENCRYPTION_KEY = os.getenv("HRC_IPFS_ENCRYPTION_KEY", "")  # Hex-encoded 32-byte key

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

    # K8s Namespace Isolation settings (for Sub-chain isolation)
    K8S_ENABLED = os.getenv("HRC_K8S_ENABLED", "false").lower() == "true"
    K8S_NAMESPACE_PREFIX = os.getenv("HRC_K8S_NAMESPACE_PREFIX", "hrc-subchain-")

    # Path to kubeconfig, empty for in-cluster
    K8S_CONFIG_PATH = os.getenv("HRC_K8S_CONFIG", "")

    K8S_RESOURCE_LIMITS_CPU = os.getenv("HRC_K8S_CPU_LIMIT", "1000m")
    K8S_RESOURCE_LIMITS_MEMORY = os.getenv("HRC_K8S_MEMORY_LIMIT", "1Gi")
    K8S_RESOURCE_REQUESTS_CPU = os.getenv("HRC_K8S_CPU_REQUEST", "250m")
    K8S_RESOURCE_REQUESTS_MEMORY = os.getenv("HRC_K8S_MEMORY_REQUEST", "256Mi")

    # Proof Aggregation Engine settings
    PROOF_AGGREGATION_ENABLED = (
        os.getenv("HRC_PROOF_AGGREGATION", "true").lower() == "true"
    )
    PROOF_BATCH_SIZE = int(os.getenv("HRC_PROOF_BATCH_SIZE", "10"))
    PROOF_BATCH_TIMEOUT = float(os.getenv("HRC_PROOF_BATCH_TIMEOUT", "30.0"))  # seconds
    PROOF_COMPRESSION_ENABLED = (
        os.getenv("HRC_PROOF_COMPRESSION", "true").lower() == "true"
    )

    # Sub-chain Rebalancing settings (Auto-splitting)
    REBALANCE_ENABLED = os.getenv("HRC_REBALANCE_ENABLED", "true").lower() == "true"

    # events/sec
    REBALANCE_THRESHOLD_EPS = int(os.getenv("HRC_REBALANCE_THRESHOLD_EPS", "1000"))

    # seconds
    REBALANCE_CHECK_INTERVAL = float(os.getenv("HRC_REBALANCE_CHECK_INTERVAL", "60.0"))
    REBALANCE_MIN_EVENTS_FOR_SPLIT = int(os.getenv("HRC_REBALANCE_MIN_EVENTS", "5000"))

    # 5 min cooldown
    REBALANCE_COOLDOWN = float(os.getenv("HRC_REBALANCE_COOLDOWN", "300.0"))

    # Cross-level State Sync settings
    CROSS_LEVEL_SYNC_ENABLED = (
        os.getenv("HRC_CROSS_LEVEL_SYNC", "true").lower() == "true"
    )
    CROSS_LEVEL_SYNC_BATCH_SIZE = int(os.getenv("HRC_CROSS_LEVEL_BATCH", "100"))
    CROSS_LEVEL_SYNC_TIMEOUT = float(os.getenv("HRC_CROSS_LEVEL_TIMEOUT", "30.0"))

    @classmethod
    def get_consensus_config(cls) -> dict[str, Any]:
        """Get consensus configuration"""
        return {
            "type": cls.CONSENSUS_TYPE,
            "validator_timeout": cls.VALIDATOR_TIMEOUT
        }

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
    def get_integration_config(cls) -> dict[str, Any]:
        """Get integration configuration"""
        return {
            "erp_enabled": cls.ERP_INTEGRATION_ENABLED,
            "supported_systems": cls.SUPPORTED_ERP_SYSTEMS
        }

    @classmethod
    def get_auth_config(cls) -> dict[str, Any]:
        """Get authentication configuration"""
        return {
            "enabled": cls.AUTH_ENABLED,
            "key_location": cls.API_KEY_LOCATION,
            "key_name": cls.API_KEY_NAME,
            "brute_force": {
                "max_failures": cls.AUTH_BRUTE_FORCE_MAX_FAILURES,
                "lockout_duration": cls.AUTH_BRUTE_FORCE_LOCKOUT_SECONDS,
                "tracking_window": cls.AUTH_BRUTE_FORCE_WINDOW_SECONDS,
            },
            "master_key": {
                "source": cls.MASTER_KEY_SOURCE,
                "key_file": cls.MASTER_KEY_FILE,
                "environment": cls.env,
            }
        }

    @classmethod
    def get_p2p_config(cls) -> dict[str, Any]:
        """Get P2P network security configuration"""
        return {
            "enabled": cls.P2P_ENABLED,
            "host": cls.P2P_HOST,
            "port": cls.P2P_PORT,
            "seed_nodes": cls.P2P_PEERS,
            "trust_policy": cls.P2P_TRUST_POLICY,
            "peer_allowlist": cls.P2P_PEER_ALLOWLIST,
            "require_signatures": cls.P2P_REQUIRE_SIGNATURES,
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

    @classmethod
    def get_ipfs_config(cls) -> dict[str, Any]:
        """Get IPFS storage configuration"""
        return {
            "enabled": cls.IPFS_ENABLED,
            "host": cls.IPFS_HOST,
            "auto_pin": cls.IPFS_AUTO_PIN,
            "timeout": cls.IPFS_TIMEOUT,
            "encryption_key": cls.IPFS_ENCRYPTION_KEY,
        }

    @classmethod
    def validate_config(cls) -> list[str]:
        """Validate configuration and return list of errors"""
        errors = []

        if cls.BLOCK_SIZE_LIMIT <= 0:
            errors.append("BLOCK_SIZE_LIMIT must be positive")

        if cls.PROOF_SUBMISSION_INTERVAL <= 0:
            errors.append("PROOF_SUBMISSION_INTERVAL must be positive")

        if cls.VALIDATOR_TIMEOUT <= 0:
            errors.append("VALIDATOR_TIMEOUT must be positive")

        if cls.DEFAULT_STORAGE_BACKEND not in ["memory", "redis", "sqlite"]:
            errors.append(
                "DEFAULT_STORAGE_BACKEND must be one of: memory, redis, sqlite"
            )

        if cls.API_PORT <= 0 or cls.API_PORT > 65535:
            errors.append("API_PORT must be between 1 and 65535")

        return errors


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
    
    # Storage - use persistent storage
    DEFAULT_STORAGE_BACKEND = "redis"
    
    # === SECURITY: Auto-enabled in production ===
    # Authentication is MANDATORY in production
    AUTH_ENABLED = os.getenv("HRC_AUTH_ENABLED", "true").lower() == "true"
    
    # Organization validation is required
    REQUIRE_ORGANIZATION_VALIDATION = True
    
    # Identity management must be on
    IDENTITY_MANAGER_ENABLED = True
    
    # MSP (Membership Service Provider) enabled
    MSP_ENABLED = True
    
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
    
    # === HTTPS: Headers enabled ===
    HSTS_ENABLED = True
    HSTS_MAX_AGE = 31536000  # 1 year
    
    # === Rate Limiting: Recommended ===
    RATE_LIMIT_ENABLED = os.getenv("HRC_RATE_LIMIT", "true").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("HRC_RATE_LIMIT_RPM", "100"))

    # === P2P: Strict trust by default in production ===
    P2P_TRUST_POLICY = "strict"
    P2P_REQUIRE_SIGNATURES = True

    # === Crypto: Secure key management in production ===
    MASTER_KEY_SOURCE = "env"  # Prefer env var in production

    # === Logging: Restrict SQL detail in production ===
    LOG_SQL_DETAIL = False


class TestingSettings(Settings):
    """Testing environment settings"""
    LOG_LEVEL = "DEBUG"
    DEFAULT_STORAGE_BACKEND = "memory"
    BLOCK_SIZE_LIMIT = 10  # Smaller blocks for testing
    PROOF_SUBMISSION_INTERVAL = 10  # Faster submissions for testing


# Get settings based on environment
def get_settings() -> Settings:
    """Get settings based on environment variable"""
    env = os.getenv("HRC_ENV", "dev").lower()
    
    if env in ("product", "production"):
        return ProductionSettings()
    elif env == "test":
        return TestingSettings()
    else:
        return DevelopmentSettings()


# Global settings instance
settings = get_settings()


def _check_auth_enabled(s) -> str | None:
    """Check AUTH_ENABLED setting."""
    if not getattr(s, 'AUTH_ENABLED', True):
        return "AUTH_ENABLED should be True in production"
    return None


def _check_cors_all(s) -> str | None:
    """Check CORS_ALLOW_ALL setting."""
    if getattr(s, 'CORS_ALLOW_ALL', False):
        return "CORS_ALLOW_ALL should be False in production"
    return None


def _check_p2p_trust(s) -> str | None:
    """Check P2P_TRUST_POLICY setting."""
    if not getattr(s, 'P2P_TRUST_POLICY', None):
        return "P2P_TRUST_POLICY not set"
    return None


def _check_hsts_enabled(s) -> str | None:
    """Check HSTS_ENABLED setting."""
    if not getattr(s, 'HSTS_ENABLED', False):
        return "HSTS_ENABLED should be True in production"
    return None


def _run_production_checks(s: Any) -> list[str]:
    """Helper to run security config checks specifically for production."""
    checks = [
        _check_auth_enabled,
        _check_cors_all,
        _check_p2p_trust,
        _check_hsts_enabled,
    ]
    results = (check(s) for check in checks)
    return [res for res in results if isinstance(res, str)]


def check_security_config() -> list[str]:
    """
    Returns the warnings list for the current config.

    This function checks the security profiles and issues an alert
    If a configuration is detected that is not safe for production.
    
    Returns:
        List of warning strings.
    """
    s = settings
    warnings = []
    
    if s.__class__.__name__ == "DevelopmentSettings" and os.getenv("HRC_ENV") is None:
        warnings.append("Configuration Risk: HRC_ENV is unset, defaulting to DevelopmentSettings with disabled authentication!")
    
    if s.env == "production":
        warnings.extend(_run_production_checks(s))
    
    return warnings
