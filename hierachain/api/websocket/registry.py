"""
Connection Registry

This module provides connection registry for tracking WebSocket connections.
"""

import asyncio
import orjson
import logging
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class WebSocketSubscription:
    """WebSocket subscription information"""
    subscription_id: str
    chain_name: str
    event_types: set[str] = field(default_factory=set)
    subscribed_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class WebSocketConnection:
    """Represents a single WebSocket connection"""
    
    def __init__(self, connection_id: str, websocket, subscription: WebSocketSubscription):
        self.connection_id = connection_id
        self.websocket = websocket
        self.subscription = subscription
        self._closed = False
        
    async def send(self, message: dict):
        """Send message to client"""
        if self._closed:
            return
            
        try:
            await self.websocket.send_text(orjson.dumps(message).decode())
        except Exception as e:
            logger.error(f"Error sending to {self.connection_id}: {e}")
            self._closed = True
            
    async def send_json(self, data: Any):
        """Send JSON data to client"""
        await self.send({"data": data, "timestamp": datetime.now().isoformat()})
        
    def close(self):
        """Mark connection as closed"""
        self._closed = True
        
    @property
    def is_closed(self) -> bool:
        """Check if connection is closed"""
        return self._closed


class ConnectionRegistry:
    """
    Manages WebSocket connections.
    Handles connection lifecycle and tracking.
    """
    
    def __init__(self, max_connections_getter=None):
        # Use getter function for dynamic max_connections
        self._max_connections_getter = max_connections_getter or (lambda: 1000)
        self.active_connections: dict[str, WebSocketConnection] = {}
        self._lock = asyncio.Lock()
        
    @property
    def count(self) -> int:
        """Get current connection count"""
        return len(self.active_connections)
    
    def is_full(self) -> bool:
        """Check if at max capacity"""
        return len(self.active_connections) >= self._max_connections_getter()
    
    async def add(self, connection_id: str, conn: WebSocketConnection) -> bool:
        """Add a new connection."""
        async with self._lock:
            if self.is_full():
                return False
            self.active_connections[connection_id] = conn
            return True
    
    async def remove(self, connection_id: str) -> WebSocketConnection | None:
        """Remove a connection."""
        async with self._lock:
            return self.active_connections.pop(connection_id, None)
    
    def get(self, connection_id: str) -> WebSocketConnection | None:
        """Get a connection by ID."""
        return self.active_connections.get(connection_id)
    
    def get_all(self) -> dict[str, WebSocketConnection]:
        """Get all connections."""
        return self.active_connections
    
    async def close_all(self):
        """Close all connections."""
        async with self._lock:
            for conn in list(self.active_connections.values()):
                try:
                    await conn.websocket.close()
                except (OSError, RuntimeError, ConnectionError):
                    pass
            self.active_connections.clear()
    
def create_connection(
    connection_id: str,
    websocket,
    chain_name: str,
    auth_token: str | None = None
) -> WebSocketConnection:
    """Create a new WebSocket connection object."""
    metadata = {"auth_token": auth_token} if auth_token else {}
    subscription = WebSocketSubscription(
        subscription_id=connection_id,
        chain_name=chain_name,
        metadata=metadata
    )
    return WebSocketConnection(connection_id, websocket, subscription)
