"""
HieraChain Ledger
=================================

A HieraChain Ledger designed for enterprise applications
with a focus on business operations rather than cryptocurrency.
"""

from hierachain.config.env_manager import init_env_config, status
from hierachain.config.version import VERSION, get_version

__version__ = get_version(VERSION)
__author__ = "Nguyễn Lê Văn Dũng"

# Initialize environment configuration on import
# This checks for existing config and creates .env.HRC.example if needed
_env_init_result = init_env_config(warn_only=True)

# Define what should be imported with "from hierachain import *"
__all__ = [
    "__author__",
    "__version__",
    "init_env_config",
    "status",
]
