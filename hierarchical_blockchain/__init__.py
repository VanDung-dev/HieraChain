"""
Hierarchical Blockchain Framework
=================================

A hierarchical blockchain framework inspired by Hyperledger Fabric architecture,
designed for enterprise applications with a focus on business operations rather than cryptocurrency.
"""

from typing import Tuple
from hierarchical_blockchain.units.version import get_version, VERSION


__version__ = get_version(VERSION)

__author__ = "Nguyễn Lê Văn Dũng"

# Define what should be imported with "from hierarchical_blockchain import *"
__all__ = []