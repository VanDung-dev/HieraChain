"""
Event validation utilities for HieraChain Ledger.

Provides domain event structure validation with required fields,
type checking, and content validation.
"""

from typing import Any


def validate_domain_event(event: dict[str, Any]) -> bool:
    required_fields = ["entity_id", "event", "timestamp"]
    if not _check_required_fields(event, required_fields):
        return False
    if not _check_field_types(event):
        return False
    if not _check_field_values(event):
        return False
    return True


def _check_required_fields(event: dict[str, Any], fields: list[str]) -> bool:
    for field in fields:
        if field not in event:
            return False
    return True


def _check_field_types(event: dict[str, Any]) -> bool:
    if not isinstance(event["timestamp"], (int, float)):
        return False
    if not isinstance(event["entity_id"], str):
        return False
    if not isinstance(event["event"], str):
        return False
    return True


def _check_field_values(event: dict[str, Any]) -> bool:
    if len(event["entity_id"].strip()) == 0:
        return False
    if len(event["event"].strip()) == 0:
        return False
    return True
