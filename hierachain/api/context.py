"""
API runtime context and shared service references.
"""

from typing import Any

_p2p_client: Any = None


def get_p2p_client() -> Any:
    """Get the active P2P NetworkClient instance."""
    return _p2p_client


def set_p2p_client(client: Any) -> None:
    """Set the active P2P NetworkClient instance."""
    global _p2p_client
    _p2p_client = client
