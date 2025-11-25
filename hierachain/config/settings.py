"""
Configuration settings for HieraChain framework.

This module provides the configuration management for the HieraChain system.
It defines settings for various components including blockchain parameters, consensus 
mechanisms, storage backends, security features, and integration capabilities.

The configuration supports multiple environments (development, production, testing) and
provides validation mechanisms to ensure system integrity.
"""

import os
from typing import Dict, Any, List
from hierachain.units.version import get_version, VERSION



class Settings:
    """Framework configuration settings"""
    
    # Framework version
    VERSION = get_version(VERSION)
    FRAMEWORK_NAME = "HieraChain"

    # Blockchain settings
    BLOCK_SIZE_LIMIT = 1000  # Maximum events per block
    PROOF_SUBMISSION_INTERVAL = 300  # 5 minutes in seconds
    
    # Consensus settings
    CONSENSUS_TYPE = "hierarchical_poa"  # Hierarchical Proof of Authority
    VALIDATOR_TIMEOUT = 30  # seconds
    BFT_ENABLED = True  # Enable Byzantine Fault Tolerance consensus
    BFT_FAULT_TOLERANCE = 1  # Number of Byzantine faults to tolerate (f)
    BFT_NODE_COUNT = 4  # Total number of nodes (must be >= 3f + 1)
    
    # Storage settings
    DEFAULT_STORAGE_BACKEND = "memory"  # memory, redis, sqlite
    WORLD_STATE_CACHE_SIZE = 1000
    
    # Advanced Caching settings
    ADVANCED_CACHING_ENABLED = True
    BLOCK_CACHE_SIZE = 5000
    EVENT_CACHE_SIZE = 20000
    ENTITY_CACHE_SIZE = 10000
    BLOCK_CACHE_POLICY = "lru"  # lru, lfu, fifo, ttl
    EVENT_CACHE_POLICY = "ttl"
    ENTITY_CACHE_POLICY = "lfu"
    ENTITY_TTL = 3600  # 1 hour in seconds
    
    # Parallel Processing settings
    PARALLEL_PROCESSING_ENABLED = True
    MAX_WORKER_THREADS = None  # Auto-detect based on CPU count
    PROCESSING_CHUNK_SIZE = 100
    
    # Security settings
    IDENTITY_MANAGER_ENABLED = True
    REQUIRE_ORGANIZATION_VALIDATION = True
    
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
    API_VERSION = "v1"
    API_HOST = "localhost"
    API_PORT = 2661
    
    # CLI settings
    CLI_CONFIG_FILE = "chains.json"
    CLI_LOG_LEVEL = "INFO"
    
    # Database settings (if using database storage)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///hierachain.db")
    
    # Redis settings (if using Redis storage)
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    
    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @classmethod
    def get_storage_config(cls) -> Dict[str, Any]:
        """Get storage configuration"""
        return {
            "backend": cls.DEFAULT_STORAGE_BACKEND,
            "cache_size": cls.WORLD_STATE_CACHE_SIZE,
            "database_url": cls.DATABASE_URL,
            "redis": {
                "host": cls.REDIS_HOST,
                "port": cls.REDIS_PORT,
                "db": cls.REDIS_DB
            }
        }
    
    @classmethod
    def get_consensus_config(cls) -> Dict[str, Any]:
        """Get consensus configuration"""
        return {
            "type": cls.CONSENSUS_TYPE,
            "validator_timeout": cls.VALIDATOR_TIMEOUT
        }
    
    @classmethod
    def get_api_config(cls) -> Dict[str, Any]:
        """Get API configuration"""
        return {
            "version": cls.API_VERSION,
            "host": cls.API_HOST,
            "port": cls.API_PORT
        }
    
    @classmethod
    def get_integration_config(cls) -> Dict[str, Any]:
        """Get integration configuration"""
        return {
            "erp_enabled": cls.ERP_INTEGRATION_ENABLED,
            "supported_systems": cls.SUPPORTED_ERP_SYSTEMS
        }
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if cls.BLOCK_SIZE_LIMIT <= 0:
            errors.append("BLOCK_SIZE_LIMIT must be positive")
        
        if cls.PROOF_SUBMISSION_INTERVAL <= 0:
            errors.append("PROOF_SUBMISSION_INTERVAL must be positive")
        
        if cls.VALIDATOR_TIMEOUT <= 0:
            errors.append("VALIDATOR_TIMEOUT must be positive")
        
        if cls.DEFAULT_STORAGE_BACKEND not in ["memory", "redis", "sqlite"]:
            errors.append("DEFAULT_STORAGE_BACKEND must be one of: memory, redis, sqlite")
        
        if cls.API_PORT <= 0 or cls.API_PORT > 65535:
            errors.append("API_PORT must be between 1 and 65535")
        
        return errors


# Environment-specific settings
class DevelopmentSettings(Settings):
    """Development environment settings"""
    LOG_LEVEL = "DEBUG"
    API_HOST = "localhost"
    DEFAULT_STORAGE_BACKEND = "memory"


class ProductionSettings(Settings):
    """Production environment settings"""
    LOG_LEVEL = "WARNING"
    API_HOST = "0.0.0.0"
    DEFAULT_STORAGE_BACKEND = "redis"
    REQUIRE_ORGANIZATION_VALIDATION = True


class TestingSettings(Settings):
    """Testing environment settings"""
    LOG_LEVEL = "DEBUG"
    DEFAULT_STORAGE_BACKEND = "memory"
    BLOCK_SIZE_LIMIT = 10  # Smaller blocks for testing
    PROOF_SUBMISSION_INTERVAL = 10  # Faster submissions for testing


# Get settings based on environment
def get_settings() -> Settings:
    """Get settings based on environment variable"""
    env = os.getenv("HBC_ENV", "dev").lower()
    
    if env == "product":
        return ProductionSettings()
    elif env == "test":
        return TestingSettings()
    else:
        return DevelopmentSettings()


# Global settings instance
settings = get_settings()