"""
Configuration module for HieraChain Ledger.

This module provides configuration management including:
- Settings (Settings, ProductionSettings, DevelopmentSettings, TestingSettings)
- Environment management (auto-configuration for .env files)
- Logging configuration
"""

from hierachain.config.env_manager import (
    ensure_product_example,
    get_current_env,
    get_env_file_path,
    has_hierachain_config,
    init_env_config,
    load_env,
    print_missing_config_warning,
    should_auto_config,
    status,
    validate_no_conflict,
)
from hierachain.config.settings import (
    DevelopmentSettings,
    ProductionSettings,
    Settings,
    TestingSettings,
    check_security_config,
    get_settings,
    settings,
)

__all__ = [
    # Environment manager
    "init_env_config",
    "ensure_product_example",
    "has_hierachain_config",
    "get_current_env",
    "load_env",
    "should_auto_config",
    "get_env_file_path",
    "status",
    "validate_no_conflict",
    "print_missing_config_warning",
    # Settings
    "Settings",
    "ProductionSettings",
    "DevelopmentSettings",
    "TestingSettings",
    "get_settings",
    "settings",
    "check_security_config",
]
