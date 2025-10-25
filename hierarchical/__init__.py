"""
Hierarchical blockchain module for Hierarchical-Blockchain Framework.

This module implements the hierarchical structure:
- MainChain: Root authority that stores proofs from Sub-Chains
- SubChain: Domain-specific chains that handle business operations
- HierarchyManager: Manages relationships between chains
- Channel: Data isolation mechanism for multi-organization collaboration
"""

from hierarchical.main_chain import MainChain
from hierarchical.sub_chain import SubChain
from hierarchical.hierarchy_manager import HierarchyManager

__all__ = ['MainChain', 'SubChain', 'HierarchyManager']
