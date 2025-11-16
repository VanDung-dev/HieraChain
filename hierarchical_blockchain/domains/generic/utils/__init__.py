"""
Generic utilities for domain operations.

This module provides utility classes for domain-specific operations:
- EntityTracer: Trace entity lifecycle across chains
- CrossChainValidator: Validate data consistency across chains
"""

from hierarchical_blockchain.domains.generic.utils.entity_tracer import EntityTracer
from hierarchical_blockchain.domains.generic.utils.cross_chain_validator import CrossChainValidator

__all__ = ['EntityTracer', 'CrossChainValidator']
