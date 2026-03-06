"""
WebSocket Endpoints for HieraChain

This module provides FastAPI WebSocket endpoints for real-time
bidirectional communication with HieraChain clients.
"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse

from hierachain.api.websocket.manager import (
    ws_manager, 
    WebSocketMessageType
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# HTML for WebSocket playground (for development)
WS_PLAYGROUND_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>HieraChain WebSocket Client</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #messages { 
            border: 1px solid #ccc; 
            height: 400px; 
            overflow-y: scroll; 
            padding: 10px; 
            margin-bottom: 10px;
            background: #f9f9f9;
        }
        .message { margin: 5px 0; padding: 5px; }
        .sent { background: #e3f2fd; }
        .received { background: #fff3e0; }
        .error { background: #ffebee; }
        .system { background: #e8f5e9; font-style: italic; }
        #status { 
            padding: 5px 10px; 
            margin-bottom: 10px;
            border-radius: 3px;
        }
        .connected { background: #c8e6c9; }
        .disconnected { background: #ffcdd2; }
        input, select, button { padding: 8px; margin: 5px 0; }
        #messageInput { width: 300px; }
    </style>
</head>
<body>
    <h1>HieraChain WebSocket Client</h1>
    
    <div id="status" class="disconnected">Disconnected</div>
    
    <div>
        <input type="text" id="chainName" placeholder="Chain name (e.g., MainChain)" value="MainChain">
        <button onclick="connect()">Connect</button>
        <button onclick="disconnect()">Disconnect</button>
    </div>
    
    <hr>
    
    <div>
        <h3>Subscribe to Chain</h3>
        <input type="text" id="subscribeChain" placeholder="Chain name">
        <input type="text" id="eventTypes" placeholder="Event types (comma separated)">
        <button onclick="subscribe()">Subscribe</button>
    </div>
    
    <hr>
    
    <div>
        <h3>Send Message</h3>
        <input type="text" id="messageInput" placeholder="Custom JSON message">
        <button onclick="sendMessage()">Send</button>
    </div>
    
    <hr>
    
    <h3>Messages</h3>
    <div id="messages"></div>
    
    <script>
        let ws = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;
        
        function connect() {
            const chainName = document.getElementById('chainName').value || 'all';
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/ws?chain_name=${encodeURIComponent(chainName)}`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                document.getElementById('status').textContent = 'Connected';
                document.getElementById('status').className = 'connected';
                addMessage('System', 'Connected to ' + wsUrl, 'system');
                reconnectAttempts = 0;
            };
            
            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    addMessage('Received', JSON.stringify(data, null, 2), 'received');
                } catch (e) {
                    addMessage('Received', event.data, 'received');
                }
            };
            
            ws.onclose = function() {
                document.getElementById('status').textContent = 'Disconnected';
                document.getElementById('status').className = 'disconnected';
                addMessage('System', 'Disconnected', 'system');
                
                // Auto reconnect
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    addMessage('System', `Reconnecting in 3 seconds... (${reconnectAttempts}/${maxReconnectAttempts})`, 'system');
                    setTimeout(connect, 3000);
                }
            };
            
            ws.onerror = function(error) {
                addMessage('Error', 'WebSocket error', 'error');
            };
        }
        
        function disconnect() {
            if (ws) {
                ws.close();
                ws = null;
            }
        }
        
        function subscribe() {
            const chain = document.getElementById('subscribeChain').value;
            const eventTypes = document.getElementById('eventTypes').value
                .split(',')
                .map(s => s.trim())
                .filter(s => s);
            
            const message = {
                type: 'subscribe',
                chain_name: chain,
                event_types: eventTypes
            };
            
            sendJson(message);
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput').value;
            try {
                const data = JSON.parse(input);
                sendJson(data);
            } catch (e) {
                addMessage('Error', 'Invalid JSON', 'error');
            }
        }
        
        function sendJson(data) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(data));
                addMessage('Sent', JSON.stringify(data, null, 2), 'sent');
            } else {
                addMessage('Error', 'Not connected', 'error');
            }
        }
        
        function addMessage(prefix, text, type) {
            const messages = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = 'message ' + type;
            div.textContent = prefix + ': ' + text;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }
    </script>
</body>
</html>
"""


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    chain_name: str | None = Query("all")
):
    """
    Main WebSocket endpoint for real-time communication.
    
    Query Parameters:
        chain_name: Chain to subscribe to (default: "all")
        
    Client Messages:
        - {"type": "subscribe", "chain_name": "...", "event_types": ["..."]}
        - {"type": "unsubscribe"}
        - {"type": "ping"}
        
    Server Messages:
        - {"type": "block_added", "chain_name": "...", "data": {...}}
        - {"type": "event", "chain_name": "...", "data": {...}}
        - {"type": "chain_status", "chain_name": "...", "data": {...}}
        - {"type": "error", "message": "..."}
        - {"type": "pong"}
    """
    connection_id = str(uuid.uuid4())
    
    # Accept the connection
    await websocket.accept()
    
    try:
        # Connect to manager
        await ws_manager.connect(
            connection_id=connection_id,
            websocket=websocket,
            chain_name=chain_name
        )
        
        # Send welcome message
        await _send_welcome_message(websocket, connection_id, chain_name)
        
        # Message loop
        await _message_loop(websocket, connection_id)
        
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        
    finally:
        # Cleanup
        await ws_manager.disconnect(connection_id)


async def _send_welcome_message(websocket: WebSocket, connection_id: str, chain_name: str):
    """Send welcome message to new connection."""
    await websocket.send_json({
        "type": "connected",
        "connection_id": connection_id,
        "message": "Connected to HieraChain WebSocket",
        "chain_name": chain_name
    })


async def _message_loop(websocket: WebSocket, connection_id: str):
    """Main message loop - handles receiving and processing messages."""
    while True:
        try:
            await _process_single_message(websocket, connection_id)
        except WebSocketDisconnect:
            break
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await ws_manager.send_to_connection(connection_id, {
                "type": WebSocketMessageType.ERROR,
                "message": "An internal error occurred"
            })


async def _process_single_message(websocket: WebSocket, connection_id: str):
    """Process a single incoming message."""
    # Receive message from client
    data = await websocket.receive_text()
    
    # Parse JSON
    message = _parse_message(data)
    if message is None:
        await _send_json_error(connection_id, "Invalid JSON")
        return
    
    # Handle message
    await handle_websocket_message(connection_id, message, websocket)


def _parse_message(data: str) -> dict | None:
    """Parse incoming JSON message."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


async def _send_json_error(connection_id: str, message: str):
    """Send error message to connection."""
    await ws_manager.send_to_connection(connection_id, {
        "type": WebSocketMessageType.ERROR,
        "message": message
    })


async def handle_websocket_message(
    connection_id: str, 
    message: dict, 
    _websocket: WebSocket
):
    """
    Handle incoming WebSocket messages from clients.
    
    Args:
        connection_id: Connection identifier
        message: Parsed message from client
        _websocket: WebSocket connection
    """
    msg_type = message.get("type", "")
    
    # Handle different message types
    if msg_type == "subscribe":
        await handle_subscribe(connection_id, message)
        
    elif msg_type == "unsubscribe":
        await handle_unsubscribe(connection_id)
        
    elif msg_type == "ping":
        await ws_manager.send_to_connection(connection_id, {
            "type": WebSocketMessageType.PONG,
            "timestamp": message.get("timestamp")
        })
        
    elif msg_type == "get_stats":
        # Return connection statistics
        stats = ws_manager.get_stats()
        await ws_manager.send_to_connection(connection_id, {
            "type": "stats",
            "data": stats
        })
        
    elif msg_type == "get_connection_info":
        # Return this connection's info
        info = ws_manager.get_connection_info(connection_id)
        await ws_manager.send_to_connection(connection_id, {
            "type": "connection_info",
            "data": info
        })
        
    else:
        await ws_manager.send_to_connection(connection_id, {
            "type": WebSocketMessageType.ERROR,
            "message": f"Unknown message type: {msg_type}"
        })


async def handle_subscribe(connection_id: str, message: dict):
    """Handle subscription request"""
    chain_name = message.get("chain_name", "all")
    event_types = message.get("event_types", [])
    
    success = await ws_manager.subscribe(
        connection_id=connection_id,
        chain_name=chain_name,
        event_types=event_types if isinstance(event_types, list) else []
    )
    
    if success:
        await ws_manager.send_to_connection(connection_id, {
            "type": "subscribed",
            "chain_name": chain_name,
            "event_types": event_types
        })
    else:
        await ws_manager.send_to_connection(connection_id, {
            "type": WebSocketMessageType.ERROR,
            "message": "Failed to subscribe"
        })


async def handle_unsubscribe(connection_id: str):
    """Handle unsubscription request"""
    success = await ws_manager.unsubscribe(connection_id)
    
    if success:
        await ws_manager.send_to_connection(connection_id, {
            "type": "unsubscribed",
            "message": "Unsubscribed from all channels"
        })
    else:
        await ws_manager.send_to_connection(connection_id, {
            "type": WebSocketMessageType.ERROR,
            "message": "Failed to unsubscribe"
        })


@router.get("/ws/playground")
async def websocket_playground():
    """WebSocket playground for testing (development only)"""
    return HTMLResponse(WS_PLAYGROUND_HTML)


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket server status and statistics"""
    stats = ws_manager.get_stats()
    return {
        "status": "running",
        "stats": stats
    }
