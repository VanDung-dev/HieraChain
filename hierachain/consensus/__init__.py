"""
Consensus module for the HieraChain framework.

This module implements a decoupled event ordering service that significantly improves 
scalability and reduces communication bandwidth. The ordering service separates event 
ordering from consensus validation, enabling enterprise-scale event volumes.

The module provides the following core components:

- OrderingService: Main orchestrator for event ordering and block creation
- OrderingNode: Configuration class for ordering service nodes
- OrderingStatus: Status enumeration for the ordering service nodes
- EventStatus: Status enumeration for event processing lifecycle
- PendingEvent: Data class representing an event awaiting processing
- EventCertifier: Component responsible for validating and certifying events
- BlockBuilder: Component that groups ordered events into blocks

The ordering service enables horizontal scaling by decoupling event ordering from 
consensus validation, allowing the system to handle higher throughput with 
reduced latency for enterprise-scale operations.
"""

from .ordering_service import (
    OrderingService,
    OrderingNode,
    OrderingStatus,
    EventStatus,
    PendingEvent,
    EventCertifier,
    BlockBuilder
)

__all__ = [
    "OrderingService",
    "OrderingNode", 
    "OrderingStatus",
    "EventStatus",
    "PendingEvent",
    "EventCertifier",
    "BlockBuilder"
]
