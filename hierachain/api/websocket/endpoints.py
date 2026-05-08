"""
WebSocket Endpoints for HieraChain

This module provides FastAPI WebSocket endpoints for real-time
bidirectional communication with HieraChain clients.
"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from hierachain.api.websocket.manager import (
    ws_manager, WebSocketMessageType
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, chain_name: str | None = Query("all")
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
    connection_id = uuid.uuid4().hex
    
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
        logger.error("WebSocket error: %s", e)
        
    finally:
        # Cleanup
        await ws_manager.disconnect(connection_id)


async def _send_welcome_message(websocket: WebSocket, connection_id: str, chain_name: str | None):
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
            logger.error("Error handling message: %s", e)
            await ws_manager.send_to_connection(
                connection_id, {
                    "type": WebSocketMessageType.ERROR,
                    "message": "An internal error occurred"
                }
            )


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
    connection_id: str, message: dict, _websocket: WebSocket
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


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket server status and statistics"""
    stats = ws_manager.get_stats()
    return {
        "status": "running",
        "stats": stats
    }
