"""
Subscription Manager

This module provides subscription management for WebSocket connections.
"""

from hierachain.api.websocket.registry import WebSocketSubscription


class SubscriptionManager:
    """
    Manages WebSocket subscriptions.
    Handles channel subscriptions (per-chain, per-event-type).
    """
    
    def __init__(self):
        # Chain subscribers: chain_name -> set of connection_ids
        self.chain_subscribers: dict[str, set[str]] = {}
        
        # Event type subscribers: (chain_name, event_type) -> set of connection_ids
        self.event_type_subscribers: dict[tuple, set[str]] = {}
        
        # All subscribers (for broadcast)
        self.all_subscribers: set[str] = set()
    
    def add_to_all(self, connection_id: str):
        """Add connection to broadcast all."""
        self.all_subscribers.add(connection_id)
    
    def remove_from_all(self, connection_id: str):
        """Remove connection from broadcast all."""
        self.all_subscribers.discard(connection_id)
    
    def subscribe_to_chain(self, connection_id: str, chain_name: str):
        """Subscribe connection to a chain."""
        if chain_name and chain_name != "all":
            if chain_name not in self.chain_subscribers:
                self.chain_subscribers[chain_name] = set()
            self.chain_subscribers[chain_name].add(connection_id)
    
    def unsubscribe_from_chain(self, connection_id: str, chain_name: str):
        """Unsubscribe connection from a chain."""
        if chain_name and chain_name != "all":
            if chain_name in self.chain_subscribers:
                self.chain_subscribers[chain_name].discard(connection_id)
    
    def subscribe_to_event_type(self, connection_id: str, chain_name: str, event_type: str):
        """Subscribe connection to an event type."""
        key = (chain_name, event_type)
        if key not in self.event_type_subscribers:
            self.event_type_subscribers[key] = set()
        self.event_type_subscribers[key].add(connection_id)
    
    def unsubscribe_from_all_event_types(self, connection_id: str, chain_name: str, event_types: set):
        """Unsubscribe connection from all event types."""
        for event_type in event_types:
            key = (chain_name, event_type)
            if key in self.event_type_subscribers:
                self.event_type_subscribers[key].discard(connection_id)
    
    def get_chain_subscribers(self, chain_name: str) -> list:
        """Get subscribers for a chain."""
        if chain_name not in self.chain_subscribers:
            return []
        return list(self.chain_subscribers[chain_name])
    
    def get_event_type_subscribers(self, chain_name: str, event_type: str) -> list:
        """Get subscribers for an event type."""
        key = (chain_name, event_type)
        if key not in self.event_type_subscribers:
            return []
        return list(self.event_type_subscribers[key])
    
    def get_all_subscribers(self) -> list:
        """Get all subscribers."""
        return list(self.all_subscribers)
    
    def has_all_subscribers(self) -> bool:
        """Check if there are any all subscribers."""
        return bool(self.all_subscribers)
    
    def get_stats(self) -> dict:
        """Get subscription statistics."""
        return {
            "chains": {
                chain: len(subscribers) 
                for chain, subscribers in self.chain_subscribers.items()
            },
            "event_types_count": len(self.event_type_subscribers)
        }
    
    def clear(self):
        """Clear all subscriptions."""
        self.chain_subscribers.clear()
        self.event_type_subscribers.clear()
        self.all_subscribers.clear()


def reset_subscription(sub: WebSocketSubscription):
    """Reset subscription to default values."""
    sub.chain_name = "all"
    sub.event_types.clear()
