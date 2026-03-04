"""
Connection Health Handlers

This module provides connection health monitoring utilities
including ping/pong handling and dead connection detection.
"""

import asyncio
import logging
import json
from typing import Callable, Awaitable
from datetime import datetime


logger = logging.getLogger(__name__)


class ConnectionHealthHandler:
    """Handles connection health monitoring and ping operations."""
    
    def __init__(
        self,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        on_connection_dead: Callable[[str], None] = None
    ):
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self._on_connection_dead = on_connection_dead
    
    async def ping_connection(self, websocket, connection_id: str) -> bool:
        """
        Ping a single connection.
        
        Returns:
            True if ping successful, False otherwise
        """
        try:
            await asyncio.wait_for(
                websocket.send_text(json.dumps({
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                })),
                timeout=self.ping_timeout
            )
            return True
        except (asyncio.TimeoutError, OSError, RuntimeError, ConnectionError):
            logger.warning(f"Ping failed for connection {connection_id}")
            return False
    
    async def check_dead_connections(
        self,
        active_connections: dict,
        disconnect_callback: Callable[[str], Awaitable[None]]
    ) -> list:
        """
        Check all connections and identify dead ones.
        
        Args:
            active_connections: Dict of connection_id -> WebSocketConnection
            disconnect_callback: Async callback to disconnect a connection
            
        Returns:
            List of dead connection IDs
        """
        dead_connections = []
        
        for connection_id, conn in active_connections.items():
            if conn.is_closed:
                dead_connections.append(connection_id)
                continue
            
            is_alive = await self.ping_connection(conn.websocket, connection_id)
            if not is_alive:
                dead_connections.append(connection_id)
        
        # Remove dead connections
        for connection_id in dead_connections:
            try:
                await disconnect_callback(connection_id)
            except Exception as e:
                logger.error(f"Error disconnecting {connection_id}: {e}")
        
        return dead_connections


class PingLoopRunner:
    """Helper class to run the ping loop in background."""
    
    def __init__(self, health_handler: ConnectionHealthHandler):
        self._health_handler = health_handler
        self._running = False
        self._task: asyncio.Task | None = None
    
    async def start(
        self,
        active_connections_getter: Callable[[], dict],
        disconnect_callback: Callable[[str], Awaitable[None]]
    ):
        """Start the ping loop."""
        self._running = True
        self._task = asyncio.create_task(
            self._run_loop(active_connections_getter, disconnect_callback)
        )
    
    @property
    def task(self) -> asyncio.Task | None:
        """Get the current ping task."""
        return self._task
    
    async def stop(self):
        """Stop the ping loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run_loop(
        self,
        active_connections_getter: Callable[[], dict],
        disconnect_callback: Callable[[str], Awaitable[None]]
    ):
        """Background task to ping connections and detect dead connections."""
        while self._running:
            try:
                await asyncio.sleep(self._health_handler.ping_interval)
                
                active_connections = active_connections_getter()
                await self._health_handler.check_dead_connections(
                    active_connections,
                    disconnect_callback
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ping loop error: {e}")
