"""
WebSocket Message Builders

This module provides utilities for building WebSocket messages
to be sent to clients.

IPFS Integration:
- Messages with off-chain data include CID references instead of full payload
- Clients can request full resolution separately via REST API
- Reduces WebSocket message size significantly
"""

from datetime import datetime
from enum import Enum

from hierachain.api.storage.utils import format_cid_display


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
    def _optimize_event_payload(event_data: dict) -> dict:
        """
        Optimize event payload for WebSocket by keeping CID references compact.

        For events with off-chain storage, this keeps only the CID reference
        instead of including full data, reducing message size.
        """
        optimized = dict(event_data)

        # Check if event has CID (off-chain storage)
        if 'details_cid' in event_data and event_data.get('details_cid'):
            # Keep CID reference, remove heavy inline details if present
            if 'details' in optimized:
                # Replace with reference indicator
                optimized['details'] = {
                    "_offchain": True,
                    "cid": format_cid_display(event_data['details_cid']),
                    "note": "Fetch via REST API with resolve_cid=true"
                }

        return optimized

    @staticmethod
    def _optimize_block_events(block_data: dict) -> dict:
        """Optimize all events in a block for WebSocket transmission."""
        optimized_block = dict(block_data)

        if 'events' in optimized_block and isinstance(optimized_block['events'], list):
            optimized_block['events'] = [
                WebSocketMessageBuilder._optimize_event_payload(event)
                for event in optimized_block['events']
            ]

        return optimized_block

    @staticmethod
    def build_block_added(chain_name: str, block_data: dict, optimize: bool = True) -> dict:
        """
        Build block added message.

        Args:
            chain_name: Name of the chain
            block_data: Block data
            optimize: If True, optimize events with CID references (default: True)

        Returns:
            WebSocket message dict
        """
        data = WebSocketMessageBuilder._optimize_block_events(block_data) if optimize else block_data

        return {
            "type": WebSocketMessageType.BLOCK_ADDED,
            "chain_name": chain_name,
            "data": data,
            "optimized": optimize,
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def build_event(
        chain_name: str,
        event_data: dict,
        event_type: str | None = None,
        optimize: bool = True
    ) -> dict:
        """
        Build event message.

        Args:
            chain_name: Name of the chain
            event_data: Event data
            event_type: Optional event type
            optimize: If True, optimize payload for off-chain data (default: True)

        Returns:
            WebSocket message dict
        """
        data = WebSocketMessageBuilder._optimize_event_payload(event_data) if optimize else event_data

        message = {
            "type": WebSocketMessageType.EVENT,
            "chain_name": chain_name,
            "data": data,
            "optimized": optimize,
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
    def build_error(error_message: str, code: str | None = None) -> dict:
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


def build_event_message(chain_name: str, event_data: dict, event_type: str | None = None) -> dict:
    """Build event message."""
    return WebSocketMessageBuilder.build_event(chain_name, event_data, event_type)
