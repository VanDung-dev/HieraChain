"""
This module provides WebSocket API endpoints for real-time communication with HieraChain.
"""

# Re-export from managers for backward compatibility
# Re-export message types and builders
from .builders import (
    WebSocketMessageBuilder,
    WebSocketMessageType,
    build_block_added,
    build_event_message,
)

# Re-export handlers
from .handlers import (
    ConnectionHealthHandler,
    PingLoopRunner,
)
from .manager import (
    WebSocketConnection,
    WebSocketManager,
    WebSocketMessage,
    WebSocketSubscription,
    ws_manager,
)

# Re-export from registry
from .registry import (
    ConnectionRegistry,
    create_connection,
)

# Re-export from subscriptions
from .subscriptions import (
    SubscriptionManager,
    reset_subscription,
)

__all__ = [
    # Manager classes
    'WebSocketManager',
    'WebSocketConnection', 
    'WebSocketSubscription',
    'WebSocketMessage',
    'ws_manager',
    
    # Registry
    'ConnectionRegistry',
    'create_connection',
    
    # Subscriptions
    'SubscriptionManager',
    'reset_subscription',
    
    # Message types
    'WebSocketMessageType',
    'WebSocketMessageBuilder',
    'build_block_added',
    'build_event_message',
    
    # Handlers
    'ConnectionHealthHandler',
    'PingLoopRunner',
]
