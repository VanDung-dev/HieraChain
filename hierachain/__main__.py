"""
Main entry point for the hierachain package.

This module allows running the HieraChain Ledger
as a module with `python -m hierachain`.
"""

from hierachain.config.env_manager import init_env_config
from hierachain.api.server import run_server


def main():
    """Main entry point function"""
    # Initialize environment configuration
    # This ensures .env has proper config if missing
    # Creates .env.example if no HRC_ config found
    init_env_config(warn_only=True)
    
    # Continue with normal startup
    run_server()


if __name__ == "__main__":
    main()
