"""
Unit tests for WebSocket functionality.

Tests the WebSocket manager and endpoints for real-time communication.
"""

import pytest
import json
from unittest.mock import AsyncMock

from hierachain.api.websocket.manager import (
    WebSocketManager,
    WebSocketConnection,
    WebSocketSubscription,
    WebSocketMessageType
)


class TestWebSocketManager:
    """Tests for WebSocketManager class"""
    
    @pytest.fixture
    def ws_manager(self):
        """Create a WebSocket manager instance"""
        return WebSocketManager(max_connections=10)
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket"""
        ws = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self, ws_manager):
        """Test manager initializes with correct defaults"""
        assert ws_manager.max_connections == 10
        assert ws_manager.connection_count == 0
        assert len(ws_manager.active_connections) == 0
        
    @pytest.mark.asyncio
    async def test_connect(self, ws_manager, mock_websocket):
        """Test connecting a new WebSocket"""
        connection_id = "test_conn_1"
        
        conn = await ws_manager.connect(
            connection_id=connection_id,
            websocket=mock_websocket,
            chain_name="MainChain"
        )
        
        assert conn is not None
        assert connection_id in ws_manager.active_connections
        assert ws_manager.connection_count == 1
        assert "MainChain" in ws_manager.chain_subscribers
        
    @pytest.mark.asyncio
    async def test_max_connections(self, ws_manager, mock_websocket):
        """Test that max connections limit is enforced"""
        ws_manager.max_connections = 2
        
        # Connect first two
        await ws_manager.connect("conn_1", mock_websocket, "chain1")
        await ws_manager.connect("conn_2", mock_websocket, "chain2")
        
        # Third should fail
        with pytest.raises(Exception, match="Maximum connections reached"):
            await ws_manager.connect("conn_3", mock_websocket, "chain3")
            
    @pytest.mark.asyncio
    async def test_disconnect(self, ws_manager, mock_websocket):
        """Test disconnecting a WebSocket"""
        connection_id = "test_conn_1"
        await ws_manager.connect(connection_id, mock_websocket, "MainChain")
        
        await ws_manager.disconnect(connection_id)
        
        assert connection_id not in ws_manager.active_connections
        assert ws_manager.connection_count == 0
        
    @pytest.mark.asyncio
    async def test_subscribe(self, ws_manager, mock_websocket):
        """Test subscribing to a chain"""
        connection_id = "test_conn_1"
        await ws_manager.connect(connection_id, mock_websocket, "default")
        
        success = await ws_manager.subscribe(
            connection_id=connection_id,
            chain_name="MainChain",
            event_types=["ORDER_CREATED", "INVENTORY_UPDATED"]
        )
        
        assert success is True
        assert connection_id in ws_manager.chain_subscribers["MainChain"]
        
    @pytest.mark.asyncio
    async def test_unsubscribe(self, ws_manager, mock_websocket):
        """Test unsubscribing from channels"""
        connection_id = "test_conn_1"
        await ws_manager.connect(connection_id, mock_websocket, "MainChain")
        
        success = await ws_manager.unsubscribe(connection_id)
        
        assert success is True
        # Should reset to "all"
        assert ws_manager.active_connections[connection_id].subscription.chain_name == "all"
        
    @pytest.mark.asyncio
    async def test_broadcast_to_chain(self, ws_manager, mock_websocket):
        """Test broadcasting to chain subscribers"""
        connection_id = "test_conn_1"
        await ws_manager.connect(connection_id, mock_websocket, "MainChain")
        
        await ws_manager.broadcast_new_block("MainChain", {"index": 1, "hash": "abc123"})
        
        # Verify message was sent
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)
        
        assert message["type"] == WebSocketMessageType.BLOCK_ADDED
        assert message["chain_name"] == "MainChain"
        
    @pytest.mark.asyncio
    async def test_broadcast_event(self, ws_manager, mock_websocket):
        """Test broadcasting events"""
        connection_id = "test_conn_1"
        await ws_manager.connect(connection_id, mock_websocket, "MainChain")
        
        event_data = {"entity_id": "order_123", "type": "ORDER_CREATED"}
        await ws_manager.broadcast_event("MainChain", event_data)
        
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)
        
        assert message["type"] == WebSocketMessageType.EVENT
        assert message["data"] == event_data
        
    @pytest.mark.asyncio
    async def test_broadcast_to_specific_event_type(self, ws_manager, mock_websocket):
        """Test broadcasting to specific event type subscribers"""
        connection_id = "test_conn_1"
        await ws_manager.connect(connection_id, mock_websocket, "MainChain")
        
        await ws_manager.subscribe(
            connection_id,
            "MainChain",
            ["ORDER_CREATED"]
        )
        
        # Broadcast to ORDER_CREATED - should receive
        await ws_manager.broadcast_event_type("MainChain", "ORDER_CREATED", {"id": 1})
        mock_websocket.send_text.assert_called()
        
    @pytest.mark.asyncio
    async def test_send_to_connection(self, ws_manager, mock_websocket):
        """Test sending message to specific connection"""
        connection_id = "test_conn_1"
        await ws_manager.connect(connection_id, mock_websocket, "MainChain")
        
        success = await ws_manager.send_to_connection(
            connection_id,
            {"type": "test", "data": "hello"}
        )
        
        assert success is True
        mock_websocket.send_text.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_send_to_nonexistent_connection(self, ws_manager):
        """Test sending to non-existent connection returns False"""
        success = await ws_manager.send_to_connection(
            "nonexistent",
            {"type": "test"}
        )
        
        assert success is False
        
    @pytest.mark.asyncio
    async def test_get_connection_info(self, ws_manager, mock_websocket):
        """Test getting connection information"""
        connection_id = "test_conn_1"
        await ws_manager.connect(connection_id, mock_websocket, "MainChain")
        
        info = ws_manager.get_connection_info(connection_id)
        
        assert info is not None
        assert info["connection_id"] == connection_id
        assert info["chain_name"] == "MainChain"
        
    @pytest.mark.asyncio
    async def test_get_stats(self, ws_manager, mock_websocket):
        """Test getting manager statistics"""
        await ws_manager.connect("conn_1", mock_websocket, "Chain1")
        await ws_manager.connect("conn_2", mock_websocket, "Chain2")
        
        stats = ws_manager.get_stats()
        
        assert stats["total_connections"] == 2
        assert stats["max_connections"] == 10
        assert "Chain1" in stats["chains"]
        assert "Chain2" in stats["chains"]
        
    @pytest.mark.asyncio
    async def test_manager_start_stop(self, ws_manager):
        """Test manager lifecycle"""
        await ws_manager.start()
        assert ws_manager._running is True
        assert ws_manager._ping_task is not None
        
        await ws_manager.stop()
        assert ws_manager._running is False


class TestWebSocketMessageType:
    """Tests for WebSocketMessageType enum"""
    
    def test_message_types(self):
        """Test all message types are defined"""
        assert WebSocketMessageType.SUBSCRIBE == "subscribe"
        assert WebSocketMessageType.UNSUBSCRIBE == "unsubscribe"
        assert WebSocketMessageType.EVENT == "event"
        assert WebSocketMessageType.BLOCK_ADDED == "block_added"
        assert WebSocketMessageType.CHAIN_STATUS == "chain_status"
        assert WebSocketMessageType.ERROR == "error"
        assert WebSocketMessageType.PING == "ping"
        assert WebSocketMessageType.PONG == "pong"
        assert WebSocketMessageType.AUTH == "auth"


class TestWebSocketSubscription:
    """Tests for WebSocketSubscription dataclass"""
    
    def test_subscription_creation(self):
        """Test subscription is created with defaults"""
        sub = WebSocketSubscription(
            subscription_id="test_1",
            chain_name="MainChain"
        )
        
        assert sub.subscription_id == "test_1"
        assert sub.chain_name == "MainChain"
        assert len(sub.event_types) == 0
        assert sub.subscribed_at is not None
        
    def test_subscription_with_event_types(self):
        """Test subscription with event types"""
        sub = WebSocketSubscription(
            subscription_id="test_1",
            chain_name="MainChain",
            event_types={"ORDER_CREATED", "INVENTORY_UPDATED"}
        )
        
        assert len(sub.event_types) == 2
        assert "ORDER_CREATED" in sub.event_types


class TestWebSocketConnection:
    """Tests for WebSocketConnection class"""
    
    @pytest.fixture
    def mock_ws(self):
        """Create mock websocket"""
        ws = AsyncMock()
        ws.send_text = AsyncMock()
        return ws
    
    @pytest.mark.asyncio
    async def test_connection_send(self, mock_ws):
        """Test sending message through connection"""
        sub = WebSocketSubscription("test_1", "MainChain")
        conn = WebSocketConnection("test_1", mock_ws, sub)
        
        await conn.send({"type": "test"})
        
        mock_ws.send_text.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_connection_send_json(self, mock_ws):
        """Test sending JSON through connection"""
        sub = WebSocketSubscription("test_1", "MainChain")
        conn = WebSocketConnection("test_1", mock_ws, sub)
        
        await conn.send_json({"key": "value"})
        
        mock_ws.send_text.assert_called_once()
        call_args = mock_ws.send_text.call_args[0][0]
        data = json.loads(call_args)
        assert data["data"]["key"] == "value"
        
    @pytest.mark.asyncio
    async def test_connection_close(self, mock_ws):
        """Test connection close"""
        sub = WebSocketSubscription("test_1", "MainChain")
        conn = WebSocketConnection("test_1", mock_ws, sub)
        
        conn.close()
        
        assert conn._closed is True
        
        # Should not send after close
        await conn.send({"type": "test"})
        mock_ws.send_text.assert_not_called()


class TestWebSocketEndpoints:
    """Tests for WebSocket endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app"""
        from fastapi import FastAPI
        from hierachain.api.websocket.endpoints import router
        
        app = FastAPI()
        app.include_router(router)
        return app
    
    @pytest.mark.asyncio
    async def test_websocket_status_endpoint(self, app):
        """Test /ws/status endpoint"""
        from fastapi.testclient import TestClient
        from hierachain.api.websocket.manager import ws_manager
        
        client = TestClient(app)
        
        # Start manager for test
        await ws_manager.start()
        
        response = client.get("/ws/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "stats" in data
        
        # Cleanup
        await ws_manager.stop()
        
    @pytest.mark.asyncio
    async def test_websocket_playground_endpoint(self, app):
        """Test /ws/playground returns HTML"""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        response = client.get("/ws/playground")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "HieraChain WebSocket Client" in response.text
