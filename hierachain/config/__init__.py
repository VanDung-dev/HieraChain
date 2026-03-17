"""
Configuration module for HieraChain Ledger.

This module provides configuration management including:
- Settings (Settings, ProductionSettings, DevelopmentSettings, TestingSettings)
- Environment management (auto-configuration for .env files)
- Logging configuration
"""

from hierachain.config.env_manager import (
    init_env_config,
    ensure_product_example,
    has_hierachain_config,
    get_current_env,
    load_env,
    should_auto_config,
    get_env_file_path,
    status,
    validate_no_conflict,
    print_missing_config_warning,
)

from hierachain.config.settings import (
    Settings,
    ProductionSettings,
    DevelopmentSettings,
    TestingSettings,
    get_settings,
    settings,
    check_security_config,
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
