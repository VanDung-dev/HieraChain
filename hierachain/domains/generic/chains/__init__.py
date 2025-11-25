"""
Generic chain implementations.

This module provides base classes for domain-specific chains:
- BaseChain: Foundation for all domain chains
- DomainChain: Generic domain-specific chain implementation
"""

from hierachain.domains.generic.chains.base_chain import BaseChain
from hierachain.domains.generic.chains.domain_chain import DomainChain

__all__ = ['BaseChain', 'DomainChain']
