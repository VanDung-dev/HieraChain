"""
Version utility functions for Hierarchical-Blockchain Framework.

This module provides functions for managing and retrieving version information.
"""

from typing import Tuple, Union, Optional

# Version information
VERSION: Tuple[int, int, int, str, int] = (0, 0, 0, "dev", 5)

# Regular expression to match PEP 440 version format
_VERSION_PATTERN = r"(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<micro>\d+))?(?:\.(?P<releaselevel>[a-z]+)(?P<serial>\d+)?)?"


def get_version(version: Optional[Tuple[int, int, int, str, int]] = None) -> str:
    """
    Return a PEP 440-compliant version number from VERSION.
    
    Args:
        version: Version tuple (major, minor, micro, releaselevel, serial)
                If not provided, uses the global VERSION tuple
        
    Returns:
        PEP 440-compliant version string
    """
    if version is None:
        version = VERSION
    major, minor, micro, releaselevel, serial = version
    
    # Build the base version string
    version_str = f"{major}.{minor}"
    if micro is not None:
        version_str += f".{micro}"
    
    # Add release level if not final
    if releaselevel != "final":
        if releaselevel == "dev":
            version_str += ".dev"
        else:
            version_str += f"-{releaselevel}"
        if serial > 0:
            version_str += str(serial)
    
    return version_str


def get_complete_version(version: Optional[Tuple[int, int, int, str, int]] = None) -> Tuple[int, int, int, str, int]:
    """
    Return a tuple of the version.
    
    Args:
        version: Version tuple (major, minor, micro, releaselevel, serial)
                If not provided, uses the global VERSION tuple
        
    Returns:
        Version tuple
    """
    if version is None:
        version = VERSION
    return version


def get_major_version(version: Optional[Tuple[int, int, int, str, int]] = None) -> str:
    """
    Return the major version number from VERSION.
    
    Args:
        version: Version tuple (major, minor, micro, releaselevel, serial)
                If not provided, uses the global VERSION tuple
        
    Returns:
        Major version string (e.g., "5.2")
    """
    if version is None:
        version = VERSION
    major, minor, _, _, _ = version
    return f"{major}.{minor}"


def get_documentation_status(version: Optional[Tuple[int, int, int, str, int]] = None) -> str:
    """
    Return the documentation status for the version.
    
    Args:
        version: Version tuple (major, minor, micro, releaselevel, serial)
                If not provided, uses the global VERSION tuple
        
    Returns:
        Documentation status string
    """
    if version is None:
        version = VERSION
    _, _, _, releaselevel, _ = version
    
    if releaselevel == "alpha":
        return "under development"
    elif releaselevel == "beta":
        return "in beta"
    elif releaselevel == "rc":
        return "release candidate"
    elif releaselevel == "final":
        return "stable"
    else:
        return "development"


def compare_versions(version1: Union[str, Tuple[int, int, int, str, int]], 
                     version2: Union[str, Tuple[int, int, int, str, int]]) -> int:
    """
    Compare two versions.
    
    Args:
        version1: First version to compare (tuple or string)
        version2: Second version to compare (tuple or string)
        
    Returns:
        -1 if version1 < version2
        0 if version1 == version2
        1 if version1 > version2
    """
    def _version_tuple(v: Union[str, Tuple[int, int, int, str, int]]) -> Tuple[int, int, int, str, int]:
        if isinstance(v, str):
            # Parse string version to tuple (simplified)
            import re
            # Match versions like "1.0.0", "1.0.0.dev", "1.0.0-alpha1", etc.
            match = re.match(_VERSION_PATTERN, v)
            if match:
                groups = match.groupdict()
                major = int(groups['major'])
                minor = int(groups['minor'])
                micro = int(groups['micro']) if groups['micro'] else 0
                releaselevel = groups['releaselevel'] or 'final'
                serial = int(groups['serial']) if groups['serial'] else 0
                
                # Special handling for dev versions
                if 'dev' in v:
                    releaselevel = 'dev'
                    # Extract serial from dev suffix if present
                    dev_parts = v.split('.dev')
                    if len(dev_parts) > 1 and dev_parts[1]:
                        serial = int(dev_parts[1])
                        
                return (major, minor, micro, releaselevel, serial)
            else:
                # Fallback for simple versions
                parts = v.split(".")
                major = int(parts[0])
                minor = int(parts[1]) if len(parts) > 1 else 0
                micro = int(parts[2]) if len(parts) > 2 else 0
                
                # Handle special cases
                if "dev" in v:
                    return (major, minor, micro, "dev", 0)
                elif "alpha" in v:
                    return (major, minor, micro, "alpha", 0)
                elif "beta" in v:
                    return (major, minor, micro, "beta", 0)
                elif "rc" in v:
                    return (major, minor, micro, "rc", 0)
                else:
                    return (major, minor, micro, "final", 0)
        return v
    
    v1 = _version_tuple(version1)
    v2 = _version_tuple(version2)
    
    # Define release level precedence
    release_levels = ["dev", "alpha", "beta", "rc", "final"]
    
    # Compare major, minor, micro
    for i in range(3):
        if v1[i] < v2[i]:
            return -1
        elif v1[i] > v2[i]:
            return 1
    
    # Compare release levels
    v1_level_idx = release_levels.index(v1[3])
    v2_level_idx = release_levels.index(v2[3])
    
    if v1_level_idx < v2_level_idx:
        return -1
    elif v1_level_idx > v2_level_idx:
        return 1
    
    # Compare serial numbers
    if v1[4] < v2[4]:
        return -1
    elif v1[4] > v2[4]:
        return 1
    
    return 0