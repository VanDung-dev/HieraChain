"""
Version management for HieraChain Ledger.
"""

from typing import Tuple

VERSION: Tuple[int, int, int, str, int] = (0, 1, 0, "dev", 1)


def _format_base_version(major: int, minor: int, micro: int | None) -> str:
    if micro is None:
        return f"{major}.{minor}"
    return f"{major}.{minor}.{micro}"


def _format_release_suffix(releaselevel: str, serial: int) -> str:
    if releaselevel == "final":
        return ""
    if releaselevel == "dev":
        prefix = ".dev"
    else:
        prefix = f"-{releaselevel}"
    return f"{prefix}{serial}" if serial > 0 else prefix


def get_version(version: Tuple[int, int, int, str, int] | None = None) -> str:
    v = version if version is not None else VERSION
    major, minor, micro, releaselevel, serial = v
    base = _format_base_version(major, minor, micro)
    suffix = _format_release_suffix(releaselevel, serial)
    return base + suffix


__version__: str = get_version(VERSION)
