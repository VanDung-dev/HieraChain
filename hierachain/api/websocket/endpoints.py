"""
WebSocket Endpoints for HieraChain

This module provides FastAPI WebSocket endpoints for real-time
bidirectional communication with HieraChain clients.
"""

import json
import logging
import uuid

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from starlette.requests import HTTPConnection

from hierachain.api.websocket.manager import WebSocketMessageType, ws_manager
from hierachain.config.settings import get_settings
from hierachain.security.verify.api_key_verifier import ResourcePermissionChecker
from hierachain.serialization import dumps_json, loads_json

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

    auth_context, authenticated = await _authenticate_connection(websocket)
    if not authenticated:
        await websocket.close(code=1008, reason="Authentication required")
        return
    if not _has_stream_permissions(auth_context):
        await websocket.close(
            code=1008,
            reason="WebSocket streaming requires chains and events permissions",
        )
        return
    
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
        await _message_loop(websocket, connection_id, auth_context)
        
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        
    finally:
        # Cleanup
        await ws_manager.disconnect(connection_id)


async def _authenticate_connection(connection: HTTPConnection) -> tuple[dict | None, bool]:
    """Authenticate a stream or status request with the app's configured verifier."""
    verifier = getattr(connection.app.state, "auth_verifier", None)
    auth_required = get_settings().AUTH_ENABLED
    if verifier is None:
        return None, not auth_required
    if not verifier.enabled:
        return None, not auth_required

    try:
        auth_context = await verifier(connection)
    except HTTPException:
        return None, False
    except Exception:
        logger.error("WebSocket authentication failed")
        return None, False
    if auth_context is None and auth_required:
        return None, False
    return auth_context, True


def _has_stream_permissions(auth_context: dict | None) -> bool:
    """The current stream sends both blocks and events to each chain subscriber."""
    if auth_context is None:
        return True
    return all(
        ResourcePermissionChecker.has_permission(auth_context, permission)
        for permission in ("chains", "events")
    )


async def _send_welcome_message(websocket: WebSocket, connection_id: str, chain_name: str | None) -> None:
    """Send welcome message to new connection."""
    await websocket.send_text(dumps_json({
        "type": "connected",
        "connection_id": connection_id,
        "message": "Connected to HieraChain WebSocket",
        "chain_name": chain_name
    }))


async def _message_loop(
    websocket: WebSocket, connection_id: str, auth_context: dict | None = None
):
    """Main message loop - handles receiving and processing messages."""
    while True:
        try:
            await _process_single_message(websocket, connection_id, auth_context)
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


async def _process_single_message(
    websocket: WebSocket, connection_id: str, auth_context: dict | None = None
):
    """Process a single incoming message."""
    # Receive message from client
    data = await websocket.receive_text()
    
    # Parse JSON
    message = _parse_message(data)
    if message is None:
        await _send_json_error(connection_id, "Invalid JSON")
        return
    
    # Handle message
    await handle_websocket_message(connection_id, message, websocket, auth_context)


def _parse_message(data: str) -> dict | None:
    """Parse incoming JSON message."""
    try:
        return loads_json(data)
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
    _websocket: WebSocket,
    auth_context: dict | None = None,
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
        await handle_subscribe(connection_id, message, auth_context)
        
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


async def handle_subscribe(
    connection_id: str, message: dict, auth_context: dict | None = None
):
    """Handle subscription request"""
    if not _has_stream_permissions(auth_context):
        await ws_manager.send_to_connection(connection_id, {
            "type": WebSocketMessageType.ERROR,
            "message": "WebSocket subscriptions require chains and events permissions",
        })
        return

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
async def websocket_status(request: Request) -> dict:
    """Get WebSocket server status and statistics"""
    auth_context, authenticated = await _authenticate_connection(request)
    if not authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    if auth_context is not None and not ResourcePermissionChecker.has_permission(auth_context, "chains"):
        raise HTTPException(status_code=403, detail="WebSocket status requires chains permission")
    stats = ws_manager.get_stats()
    return {
        "status": "running",
        "stats": stats
    }
