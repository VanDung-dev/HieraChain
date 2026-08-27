"""
Environment Manager for HieraChain

This module provides automatic configuration management for the HieraChain system.
It checks for existing .env files and suggests Product configuration via
.env.HRC.example if no HieraChain configuration is detected.

Usage:
    from hierachain.config.env_manager import init_env_config, ensure_product_config
    
    # Call at application startup
    init_env_config()
"""

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# Constants
ENV_FILE = Path(".env")
ENV_EXAMPLE_FILE = Path(".env.HRC.example")
HRC_PREFIX = "HRC_"

# Environment variable to track if warning has been shown
_WARNING_ENV_VAR = "HRC_WARNING_SHOWN"

# Default Product configuration - loaded from .env.HRC.example file
# NOTE: SQLite is used as default for development ease.
# For production, consider using PostgreSQL, MySQL, or other supported databases.
# See hierachain/adapters/database/ for available adapters.


def get_product_config_template() -> str:
    """
    Get the Product configuration template.
    
    This function imports the template from the Python module to ensure
    it works both in development and when installed as a pip package.
    
    Returns:
        The Product configuration template string
    """
    try:
        from hierachain.config.product_config_template import PRODUCT_CONFIG_TEMPLATE
        return PRODUCT_CONFIG_TEMPLATE
    except ImportError:
        # Fallback: raise error if module not found
        raise FileNotFoundError("Could not find Product config template module")


def has_hierachain_config(env_file: Optional[Path] = ENV_FILE) -> bool:
    """
    Check if .env file has any HieraChain configuration.
    
    Checks for any environment variable starting with HRC_ prefix.
    
    Args:
        env_file: Path to .env file
        
    Returns:
        True if HRC_ configuration exists, False otherwise
    """
    if env_file is None or not env_file.exists():
        return False
    
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Check for any HRC_ environment variables (excluding comments)
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith('#') and line.startswith(HRC_PREFIX):
            return True
    return False


def get_current_env(env_file: Optional[Path] = ENV_FILE) -> Optional[str]:
    """
    Get current HRC_ENV value from .env file.
    
    Args:
        env_file: Path to .env file
        
    Returns:
        Current environment value or None if not set
    """
    if env_file is None or not env_file.exists():
        return None
    
    with open(env_file, 'r') as f:
        lines = (line.strip() for line in f if line.strip() and not line.startswith('#'))
        match = next((line for line in lines if line.startswith('HRC_ENV=')), None)
        return match.split('=', 1)[1].strip() if match else None


def get_current_env_from_os() -> Optional[str]:
    """
    Get current HRC_ENV value from os.environ.
    
    Returns:
        Current environment value or None if not set
    """
    return os.getenv('HRC_ENV') or os.getenv('ENV')


def validate_no_conflict(env_file: Path) -> list[str]:
    """
    Validate that new config doesn't conflict with existing settings.
    
    Returns list of warnings (empty if no conflicts)
    """
    warnings = []
    
    current_env = get_current_env(env_file)
    if current_env and current_env != 'product':
        warnings.append(
            f"Existing HRC_ENV='{current_env}' will be overridden to 'product'"
        )
    
    return warnings


def ensure_product_example(env_example_file: Optional[Path] = ENV_EXAMPLE_FILE) -> bool:
    """
    Ensure .env.HRC.example file exists with Product configuration.
    
    This function creates .env.HRC.example with Product configuration template
    if it doesn't exist or doesn't have HRC_ configuration.
    
    Args:
        env_example_file: Path to .env.HRC.example file
        
    Returns:
        True if example file was created/updated, False if already exists
    """
    if env_example_file is None:
        return False
    
    # Reuse has_hierachain_config to check existing HRC_ config
    if has_hierachain_config(env_example_file):
        return False
    
    # Create/update .env.HRC.example with Product config
    template_content = get_product_config_template()
    with open(env_example_file, 'w') as f:
        f.write(template_content)
    
    return True


def load_env(env_file: Optional[Path] = ENV_FILE) -> bool:
    """
    Load .env file into os.environ.
    
    Args:
        env_file: Path to .env file
        
    Returns:
        True if file was loaded, False if not found
    """
    if env_file is None or not env_file.exists():
        return False
    
    load_dotenv(env_file)
    return True


def should_auto_config() -> bool:
    """
    Check if auto-configuration should be enabled.
    
    Can be disabled via HRC_AUTO_CONFIG=false environment variable.
    
    Returns:
        True if auto-config is enabled (default), False otherwise
    """
    auto_config = os.getenv('HRC_AUTO_CONFIG', 'true').lower()
    return auto_config != 'false'


def get_env_file_path() -> Path:
    """
    Get the path to the .env file.
    
    Can be customized via HRC_ENV_FILE environment variable.
    
    Returns:
        Path to the .env file
    """
    env_file_path = os.getenv('HRC_ENV_FILE', '.env')
    return Path(env_file_path)


def print_missing_config_warning():
    """Print warning message about missing configuration."""
    # Only print warning once (using env var to work across uvicorn processes)
    if os.getenv(_WARNING_ENV_VAR):
        return
    os.environ[_WARNING_ENV_VAR] = "1"
    
    print("=" * 60, file=sys.stderr)
    print("WARNING: No HieraChain configuration found!", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(file=sys.stderr)
    print("To configure HieraChain for production, please:", file=sys.stderr)
    print("  1. Copy '.env.HRC.example' to '.env':", file=sys.stderr)
    print("     cp .env.HRC.example .env", file=sys.stderr)
    print("  2. Review and customize the configuration in '.env'", file=sys.stderr)
    print("  3. Restart the application", file=sys.stderr)
    print(file=sys.stderr)
    print("Alternatively, set HRC_ENV=dev for development mode.", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


def init_env_config(
    env_file: Optional[Path] = None,
    env_example_file: Optional[Path] = None,
    auto_config: Optional[bool] = None,
    warn_only: bool = True
) -> bool:
    """
    Initialize environment configuration.
    
    This is the main entry point for environment configuration.
    It checks if configuration exists and suggests .env.HRC.example if needed.
    
    Args:
        env_file: Path to .env file (defaults to HRC_ENV_FILE or .env)
        env_example_file: Path to .env.HRC.example file (defaults to .env.HRC.example)
        auto_config: Override auto-config setting (defaults to HRC_AUTO_CONFIG)
        warn_only: If True, only warn about missing config instead of modifying files
        
    Returns:
        True if .env.HRC.example was created/updated, False otherwise
    """
    if os.getenv("HRC_ENV", "").lower() in ("test", "testing"):
        return False
    if os.getenv("PYTEST_CURRENT_TEST") is not None or "pytest" in sys.modules:
        return False
    # Determine settings
    if env_file is None:
        env_file = get_env_file_path()
    
    if env_example_file is None:
        env_example_file = ENV_EXAMPLE_FILE
    
    if auto_config is None:
        auto_config = should_auto_config()
    
    # If auto-config is disabled, just load existing .env
    if not auto_config:
        load_env(env_file)
        return False
    
    # Check if we have existing HRC_ config
    has_config = has_hierachain_config(env_file)
    
    if has_config:
        # Config exists, just load .env
        load_env(env_file)
        return False
    
    # No config found - create .env.HRC.example (safe approach)
    example_created = ensure_product_example(env_example_file)
    
    # Load existing .env if it exists
    load_env(env_file)
    
    # Show warning to user
    if warn_only:
        print_missing_config_warning()
    
    return example_created


# Convenience function for CLI usage
def status(env_file: Path = ENV_FILE) -> dict:
    """
    Get status of environment configuration.
    
    Args:
        env_file: Path to .env file
        
    Returns:
        Dictionary with status information
    """
    has_config = has_hierachain_config(env_file)
    current_env = get_current_env(env_file) or get_current_env_from_os()
    example_exists = ENV_EXAMPLE_FILE.exists()
    
    return {
        'env_file_exists': env_file.exists(),
        'has_hrc_config': has_config,
        'current_env': current_env,
        'auto_config_enabled': should_auto_config(),
        'example_file_exists': example_exists,
    }
