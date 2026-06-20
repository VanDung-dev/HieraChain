"""
Version utility functions for HieraChain Ledger.

This module provides functions for managing and retrieving version information.
"""

from typing import Tuple
import re

VERSION: Tuple[int, int, int, str, int] = (0, 0, 5, "final", 0)

_VERSION_PATTERN = (
    r"""
    (?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<micro>\d+))?(?:\.(?P<releaselevel>[a-z]+)(?P<serial>\d+)?)?
    """
)
_RELEASE_LEVEL_ORDER: dict[str, int] = {
    "dev": 0, "alpha": 1, "beta": 2, "rc": 3, "final": 4
}


def _format_base_version(major: int, minor: int, micro: int | None) -> str:
    """Format the base version string without release level or serial number."""
    if micro is None:
        return f"{major}.{minor}"
    return f"{major}.{minor}.{micro}"


def _format_release_suffix(releaselevel: str, serial: int) -> str:
    """
    Format the release suffix based on release level and serial number.
    Returns an empty string for 'final' release level.
    """
    if releaselevel == "final":
        return ""
    if releaselevel == "dev":
        prefix = ".dev"
    else:
        prefix = f"-{releaselevel}"
    return f"{prefix}{serial}" if serial > 0 else prefix


def get_version(version: Tuple[int, int, int, str, int] | None = None) -> str:
    """
    Return a PEP 440-compliant version number from VERSION.
    
    Args:
        version: Version tuple (major, minor, micro, releaselevel, serial)
                If not provided, uses the global VERSION tuple
        
    Returns:
        PEP 440-compliant version string
    """
    v = version if version is not None else VERSION
    major, minor, micro, releaselevel, serial = v
    base = _format_base_version(major, minor, micro)
    suffix = _format_release_suffix(releaselevel, serial)
    return base + suffix


def get_complete_version(
    version: Tuple[int, int, int, str, int] | None = None
) -> Tuple[int, int, int, str, int]:
    """
    Return a tuple of the version.
    
    Args:
        version: Version tuple (major, minor, micro, releaselevel, serial)
                If not provided, uses the global VERSION tuple
        
    Returns:
        Version tuple
    """
    v = version if version is not None else VERSION
    return v


def get_major_version(version: Tuple[int, int, int, str, int] | None = None) -> str:
    """
    Return the major version number from VERSION.
    
    Args:
        version: Version tuple (major, minor, micro, releaselevel, serial)
                If not provided, uses the global VERSION tuple
        
    Returns:
        Major version string (e.g., "5.2")
    """
    v = version if version is not None else VERSION
    major, minor, _, _, _ = v
    return f"{major}.{minor}"


def get_documentation_status(version: Tuple[int, int, int, str, int] | None) -> str:
    """
    Return the documentation status for the version.
    
    Args:
        version: Version tuple (major, minor, micro, releaselevel, serial)
                If not provided, uses the global VERSION tuple
        
    Returns:
        Documentation status string
    """
    v = version if version is not None else VERSION
    _, _, _, releaselevel, _ = v
    
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


def _apply_dev_overrides(
    v: str, base: Tuple[int, int, int, str, int]
) -> Tuple[int, int, int, str, int]:
    """
    Apply overrides for development versions, handling serial numbers and dev suffixes.
    """
    major, minor, micro, releaselevel, serial = base
    if "dev" not in v:
        return base
    releaselevel = "dev"
    dev_parts = v.split(".dev")
    if len(dev_parts) > 1 and dev_parts[1]:
        try:
            serial = int(dev_parts[1])
        except ValueError:
            pass
    return major, minor, micro, releaselevel, serial


def _parse_with_pattern(v: str) -> Tuple[int, int, int, str, int] | None:
    """
    Attempt to parse version string using a regular expression pattern.
    Returns None if the pattern does not match.
    """
    match = re.match(_VERSION_PATTERN, v)
    if not match:
        return None
    groups = match.groupdict()
    major = int(groups["major"])
    minor = int(groups["minor"])
    micro = int(groups["micro"]) if groups["micro"] else 0
    releaselevel = groups["releaselevel"] or "final"
    serial = int(groups["serial"]) if groups["serial"] else 0
    base = (major, minor, micro, releaselevel, serial)
    return _apply_dev_overrides(v, base)


def _fallback_version_parse(v: str) -> Tuple[int, int, int, str, int]:
    """
    Fallback version parsing for strings that do not match the regular
    expression pattern.
    Handles simple version formats without release level or serial numbers.
    """
    parts = v.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    micro = int(parts[2]) if len(parts) > 2 else 0

    for key, level in (
        ("dev", "dev"), ("alpha", "alpha"), ("beta", "beta"), ("rc", "rc")
    ):
        if key in v:
            return major, minor, micro, level, 0
    return major, minor, micro, "final", 0


def _parse_version_string(v: str) -> Tuple[int, int, int, str, int]:
    """
    Parses a version string into a tuple of (major, minor, micro, releaselevel, serial).
    Uses a regular expression pattern for parsing, falling back to a simple format if
    necessary.
    """
    parsed = _parse_with_pattern(v)
    if parsed is not None:
        return parsed
    return _fallback_version_parse(v)


def _version_tuple(
    v: str | Tuple[int, int, int, str, int]
) -> Tuple[int, int, int, str, int]:
    """
    Converts a version string or tuple to a version tuple.
    If the input is already a tuple, it is returned as is.
    """
    if isinstance(v, str):
        return _parse_version_string(v)
    return v


def _normalize_version_tuple(
    v: Tuple[int, int, int, str, int]
) -> Tuple[int, int, int, int, int]:
    """
    Normalize a version tuple by converting release level to an integer for comparison.
    """
    major, minor, micro, level, serial = v
    return major, minor, micro, _RELEASE_LEVEL_ORDER[level], serial


def _compare_version_tuples(
    v1: Tuple[int, int, int, str, int], v2: Tuple[int, int, int, str, int]
) -> int:
    """
    Compares two version tuples and returns -1, 0, or 1 based on their order.
    """
    n1 = _normalize_version_tuple(v1)
    n2 = _normalize_version_tuple(v2)
    return (n1 > n2) - (n1 < n2)


def compare_versions(
    version1: str | Tuple[int, int, int, str, int],
    version2: str | Tuple[int, int, int, str, int]
) -> int:
    """
    Compares two version strings or tuples and returns -1, 0, or 1 based on their order.
    """
    v1 = _version_tuple(version1)
    v2 = _version_tuple(version2)
    return _compare_version_tuples(v1, v2)


__version__: str = get_version(VERSION)
