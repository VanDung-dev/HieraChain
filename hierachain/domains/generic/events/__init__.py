"""
Generic event implementations.

This module provides base classes for domain-specific events:
- BaseEvent: Foundation for all domain events
- DomainEvent: Generic domain-specific event implementation
"""

from hierachain.domains.generic.events.base_event import BaseEvent
from hierachain.domains.generic.events.domain_event import DomainEvent

__all__ = ['BaseEvent', 'DomainEvent']
