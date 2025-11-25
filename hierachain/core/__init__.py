"""
Core module for HieraChain Framework.

This module contains the fundamental blockchain components:
- Block: Block structure with multiple events
- Blockchain: Base blockchain class
- Consensus mechanisms: PoA and other consensus algorithms
- Utilities: Helper functions for blockchain operations
"""

from hierachain.core.block import Block
from hierachain.core.blockchain import Blockchain

__all__ = ['Block', 'Blockchain']
