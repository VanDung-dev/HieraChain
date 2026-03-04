"""
WebSocket Message Builders

This module provides utilities for building WebSocket messages
to be sent to clients.
"""

from datetime import datetime
from enum import Enum


class WebSocketMessageType(str, Enum):
    """WebSocket message types"""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    EVENT = "event"
    BLOCK_ADDED = "block_added"
    CHAIN_STATUS = "chain_status"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    AUTH = "auth"


class WebSocketMessageBuilder:
    """Helper class to build WebSocket messages."""
    
    @staticmethod
    def build_block_added(chain_name: str, block_data: dict) -> dict:
        """Build block added message."""
        return {
            "type": WebSocketMessageType.BLOCK_ADDED,
            "chain_name": chain_name,
            "data": block_data,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def build_event(chain_name: str, event_data: dict, event_type: str = None) -> dict:
        """Build event message."""
        message = {
            "type": WebSocketMessageType.EVENT,
            "chain_name": chain_name,
            "data": event_data,
            "timestamp": datetime.now().isoformat()
        }
        if event_type:
            message["event_type"] = event_type
        return message
    
    @staticmethod
    def build_ping() -> dict:
        """Build ping message."""
        return {
            "type": WebSocketMessageType.PING,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def build_error(error_message: str, code: str = None) -> dict:
        """Build error message."""
        message = {
            "type": WebSocketMessageType.ERROR,
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        }
        if code:
            message["code"] = code
        return message


# Module-level builder functions for backward compatibility
def build_block_added(chain_name: str, block_data: dict) -> dict:
    """Build block added message."""
    return WebSocketMessageBuilder.build_block_added(chain_name, block_data)


def build_event_message(chain_name: str, event_data: dict, event_type: str = None) -> dict:
    """Build event message."""
    return WebSocketMessageBuilder.build_event(chain_name, event_data, event_type)
