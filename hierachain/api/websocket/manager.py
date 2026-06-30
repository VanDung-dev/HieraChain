"""
WebSocket Manager for HieraChain

This module provides WebSocket connection management for real-time
bidirectional communication with HieraChain clients.
"""

import asyncio
import json
import logging
from typing import Any, cast
from dataclasses import dataclass, field
from datetime import datetime

from .registry import ConnectionRegistry, WebSocketConnection, WebSocketSubscription, create_connection
from .subscriptions import SubscriptionManager, reset_subscription
from .builders import build_block_added, build_event_message
from .handlers import ConnectionHealthHandler, PingLoopRunner
from .builders import WebSocketMessageType

logger = logging.getLogger(__name__)


@dataclass 
class WebSocketMessage:
    """WebSocket message structure"""
    type: str
    data: Any = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class WebSocketManager:
    """
    Manages WebSocket connections and subscriptions for HieraChain.
    
    This class handles:
    - Connection lifecycle (connect/disconnect)
    - Channel subscriptions (per-chain, per-event-type)
    - Broadcasting messages to subscribed clients
    - Connection health monitoring
    """
    
    def __init__(
        self, 
        max_connections: int = 1000,
        ping_interval: int = 30,
        ping_timeout: int = 10
    ):
        self.max_connections = max_connections
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        
        # Use separate managers for cleaner code
        self._registry = ConnectionRegistry(lambda: self.max_connections)
        self._subscriptions = SubscriptionManager()
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        # Health handler
        self._health_handler = ConnectionHealthHandler(
            ping_interval=ping_interval,
            ping_timeout=ping_timeout
        )
        
        # Background tasks
        self._ping_runner: PingLoopRunner | None = None
        self._running = False
        
    @property
    def active_connections(self) -> dict:
        """Get active connections for external access."""
        return self._registry.get_all()
        
    @property
    def connection_count(self) -> int:
        """Get current connection count"""
        return self._registry.count
        
    @property
    def chain_subscribers(self) -> dict:
        """Get chain subscribers for stats."""
        return self._subscriptions.chain_subscribers
        
    @property
    def event_type_subscribers(self) -> dict:
        """Get event type subscribers for stats."""
        return self._subscriptions.event_type_subscribers
        
    @property
    def all_subscribers(self) -> set:
        """Get all subscribers."""
        return self._subscriptions.all_subscribers
        
    @property
    def _ping_task(self) -> asyncio.Task | None:
        """Backward compatibility property for _ping_task."""
        if self._ping_runner and self._ping_runner.task:
            return self._ping_runner.task
        return None
        
    async def start(self):
        """Start the WebSocket manager"""
        self._running = True
        self._ping_runner = PingLoopRunner(self._health_handler)
        await self._ping_runner.start(
            self._registry.get_all,
            self.disconnect
        )
        logger.info(f"WebSocket manager started with max_connections={self.max_connections}")
        
    async def stop(self):
        """Stop the WebSocket manager"""
        self._running = False
        
        if self._ping_runner:
            await self._ping_runner.stop()
                
        await self._registry.close_all()
        self._subscriptions.clear()
        
        logger.info("WebSocket manager stopped")

    # ==================== Connection Management ====================
    
    async def connect(
        self, 
        connection_id: str, 
        websocket,
        chain_name: str = "all",
        auth_token: str | None = None
    ) -> WebSocketConnection:
        """Add a new WebSocket connection."""
        async with self._lock:
            if self._registry.is_full():
                raise Exception("Maximum connections reached")
            
            conn = create_connection(connection_id, websocket, chain_name, auth_token)
            await self._registry.add(connection_id, conn)
            
            # Register subscription
            self._subscriptions.add_to_all(connection_id)
            self._subscriptions.subscribe_to_chain(connection_id, chain_name)
            
            logger.info(f"WebSocket connected: {connection_id} (total: {self._registry.count})")
            return conn

    async def disconnect(self, connection_id: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            conn = self._registry.get(connection_id)
            if not conn:
                return
            
            sub = conn.subscription
            
            # Unregister subscription
            self._subscriptions.unsubscribe_from_chain(connection_id, sub.chain_name)
            self._subscriptions.unsubscribe_from_all_event_types(
                connection_id, sub.chain_name, sub.event_types
            )
            self._subscriptions.remove_from_all(connection_id)
            
            await self._registry.remove(connection_id)
            
            logger.info(f"WebSocket disconnected: {connection_id} (remaining: {self._registry.count})")

    # ==================== Subscription Management ====================

    async def subscribe(
        self, 
        connection_id: str, 
        chain_name: str,
        event_types: list[str] | None = None
    ) -> bool:
        """Subscribe a connection to a chain and optionally specific event types."""
        async with self._lock:
            conn = self._registry.get(connection_id)
            if not conn:
                return False
            
            old_chain = conn.subscription.chain_name
            new_event_types = set(event_types) if event_types else set()
            
            # Remove from old subscriptions
            self._subscriptions.unsubscribe_from_chain(connection_id, old_chain)
            self._subscriptions.unsubscribe_from_all_event_types(
                connection_id, old_chain, cast(Any, conn.subscription.event_types)
            )
            
            # Update subscription
            conn.subscription.chain_name = chain_name
            if event_types:
                conn.subscription.event_types = new_event_types
                
            # Add to new subscriptions
            self._subscriptions.subscribe_to_chain(connection_id, chain_name)
            for event_type in new_event_types:
                self._subscriptions.subscribe_to_event_type(
                    connection_id, chain_name, event_type
                )
                
            logger.info(f"Connection {connection_id} subscribed to {chain_name}")
            return True

    async def unsubscribe(self, connection_id: str) -> bool:
        """Unsubscribe a connection from all channels"""
        async with self._lock:
            conn = self._registry.get(connection_id)
            if not conn:
                return False
            
            sub = conn.subscription
            
            self._subscriptions.unsubscribe_from_chain(connection_id, sub.chain_name)
            self._subscriptions.unsubscribe_from_all_event_types(
                connection_id, sub.chain_name, sub.event_types
            )
            reset_subscription(sub)
            
            return True

    # ==================== Broadcasting ====================

    async def broadcast_to_chain(self, chain_name: str, message: dict):
        """Broadcast a message to all subscribers of a specific chain."""
        subscribers = self._subscriptions.get_chain_subscribers(chain_name)
        if not subscribers:
            return
        await self._send_to_subscribers(subscribers, message)
            
    async def _send_to_subscribers(self, subscribers: list, message: dict):
        """Send message to list of subscriber connections"""
        message_json = json.dumps(message)
        
        for connection_id in subscribers:
            conn = self._registry.get(connection_id)
            if conn and not conn.is_closed:
                try:
                    await conn.websocket.send_text(message_json)
                except Exception as e:
                    logger.error(f"Broadcast error to {connection_id}: {e}")

    async def broadcast_to_event_type(
        self, 
        chain_name: str, 
        event_type: str, 
        message: dict
    ):
        """Broadcast to subscribers of a specific event type within a chain"""
        subscribers = self._subscriptions.get_event_type_subscribers(chain_name, event_type)
        if not subscribers:
            return
        await self._send_to_subscribers(subscribers, message)

    async def broadcast_new_block(self, chain_name: str, block_data: dict):
        """Broadcast a new block to chain subscribers."""
        message = build_block_added(chain_name, block_data)
        await self.broadcast_to_chain(chain_name, message)
        
    async def broadcast_event(self, chain_name: str, event_data: dict):
        """Broadcast a new event to chain subscribers."""
        message = build_event_message(chain_name, event_data)
        await self.broadcast_to_chain(chain_name, message)
        
    async def broadcast_event_type(
        self, 
        chain_name: str, 
        event_type: str, 
        event_data: dict
    ):
        """Broadcast event to specific event type subscribers"""
        message = build_event_message(chain_name, event_data, event_type)
        await self.broadcast_to_event_type(chain_name, event_type, message)
        
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self._subscriptions.has_all_subscribers():
            return
        subscribers = self._subscriptions.get_all_subscribers()
        await self._send_to_subscribers(subscribers, message)

    async def send_to_connection(self, connection_id: str, message: dict) -> bool:
        """Send a message to a specific connection"""
        conn = self._registry.get(connection_id)
        if not conn or conn.is_closed:
            return False
            
        try:
            await conn.websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Send error to {connection_id}: {e}")
            return False

    # ==================== Info & Stats ====================

    def get_connection_info(self, connection_id: str) -> dict | None:
        """Get information about a connection"""
        conn = self._registry.get(connection_id)
        if not conn:
            return None
            
        return {
            "connection_id": connection_id,
            "chain_name": conn.subscription.chain_name,
            "event_types": list(conn.subscription.event_types),
            "subscribed_at": conn.subscription.subscribed_at.isoformat(),
            "metadata": conn.subscription.metadata
        }
        
    def get_stats(self) -> dict:
        """Get WebSocket manager statistics"""
        sub_stats = self._subscriptions.get_stats()
        return {
            "total_connections": self._registry.count,
            "max_connections": self.max_connections,
            "chains": sub_stats["chains"],
            "event_types_count": sub_stats["event_types_count"]
        }


# Global instance
ws_manager = WebSocketManager()


# Backward compatibility exports
__all__ = [
    'WebSocketManager',
    'WebSocketConnection',
    'WebSocketSubscription',
    'WebSocketMessage',
    'WebSocketMessageType',
    'ws_manager',
]
