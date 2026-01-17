"""
Security module for HieraChain framework.
"""

from hierachain.security.identity import IdentityManager, IdentityError
from hierachain.security.resource_guard import ResourceGuardMiddleware

__all__ = [
    'IdentityManager',
    'IdentityError',
    'ResourceGuardMiddleware'
]