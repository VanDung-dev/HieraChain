"""
Backward-compat re-export shim — prefer `hierachain.domains.chains` imports.
"""

from hierachain.domains.chains import BaseChain, DomainChain


__all__ = ["BaseChain", "DomainChain"]
