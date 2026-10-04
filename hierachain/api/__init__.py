"""
API module for HieraChain Ledger
"""

from typing import Any

from hierachain.api import admin, business, ledger
from hierachain.api.blockchain_explorer import BlockchainExplorer
from hierachain.api.websocket.manager import (
    WebSocketConnection,
    WebSocketManager,
    WebSocketMessageType,
    WebSocketSubscription,
)


def __getattr__(name: str) -> Any:
    """Load server exports only when requested, keeping client imports independent."""
    if name in {"app", "create_app"}:
        from hierachain.api import server

        return getattr(server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'BlockchainExplorer',
    'WebSocketConnection',
    'WebSocketManager',
    'WebSocketMessageType',
    'WebSocketSubscription',
    'admin',
    'app',
    'business',
    'create_app',
    'ledger'
]
