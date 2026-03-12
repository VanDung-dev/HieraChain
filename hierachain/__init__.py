"""
HieraChain Ledger
=================================

A HieraChain Ledger designed for enterprise applications 
with a focus on business operations rather than cryptocurrency.
"""

from hierachain.units.version import get_version, VERSION
from hierachain.config.env_manager import init_env_config, status


__version__ = get_version(VERSION)

__author__ = "Nguyễn Lê Văn Dũng"

# Initialize environment configuration on import
# This checks for existing config and creates .env.HRC.example if needed
_env_init_result = init_env_config(warn_only=True)

# Define what should be imported with "from hierachain import *"
__all__ = [
    "__version__",
    "__author__",
    "status",
    "init_env_config",
]
