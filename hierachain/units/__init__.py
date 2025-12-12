"""
Version module for HieraChain.
"""

from .version import (
    get_version, 
    get_complete_version, 
    get_major_version, 
    get_documentation_status, 
    compare_versions
)

__all__ = [
    'get_version', 
    'get_complete_version', 
    'get_major_version', 
    'get_documentation_status', 
    'compare_versions'
]