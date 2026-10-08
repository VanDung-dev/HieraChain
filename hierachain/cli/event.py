"""
Event management commands.
"""

import json
import time
from typing import Any

import click

from hierachain.cli.store import get_sub_chain
from hierachain.serialization import loads_json


@click.group()
def event_group():
    """Event management commands."""


@event_group.command(name="add")
@click.argument('chain_name')
@click.argument(
    'event_type',
    type=click.Choice(
        ['start_operation', 'complete_operation', 'quality_check', 'status_change']
    )
)
@click.option('--entity-id', required=True, help='Entity ID')
@click.option('--details', help='Additional details as JSON string')
@click.pass_context
def add_event(
    ctx: click.Context,
    chain_name: str,
    event_type: str,
    entity_id: str,
    details: str | None,
) -> None:
    """Add an event to a durably registered sub-chain."""
    try:
        chain = get_sub_chain(ctx, chain_name)
        if not chain:
            raise click.ClickException(f"Sub-chain not found: {chain_name}")
        
        # Parse additional details
        event_details: dict[str, Any] = {}
        if details:
            try:
                parsed_details = loads_json(details)
            except json.JSONDecodeError as exc:
                raise click.ClickException("Invalid JSON format for details") from exc
            if not isinstance(parsed_details, dict):
                raise click.ClickException("Event details must be a JSON object")
            event_details = parsed_details
        
        # Create event based on type
        event = _create_event_payload(event_type, entity_id, event_details)
        if not event:
            raise click.ClickException(f"Unknown event type: {event_type}")
            
        # Add event to chain
        event_id = _append_event_to_chain(chain, event)
        
        click.echo(
            f"Added '{event_type}' event for entity {entity_id} to chain {chain_name} "
            f"(event ID: {event_id})"
        )
        
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Could not add event: {exc}") from exc


def _create_event_payload(
    event_type: str, entity_id: str, event_details: dict[str, Any]
) -> dict[str, Any] | None:
    """Helper to create event payload based on type"""
    timestamp = time.time()
    event = {
        "entity_id": entity_id,
        "event": "unknown",
        "timestamp": timestamp,
        "details": event_details
    }
    
    if event_type == 'start_operation':
        resource_id = 1 + (hash(entity_id) % 10)
        event["event"] = "operation_start"
        event["details"] = {
            "resource": f"RESOURCE-{resource_id}",
            **event_details
        }
    elif event_type == 'complete_operation':
        event["event"] = "operation_complete"
    elif event_type == 'quality_check':
        event["event"] = "quality_check"
        event["details"] = {
            "result": event_details.get("result", "pass"),
            **event_details
        }
    elif event_type == 'status_change':
        event["event"] = "status_change"
        event["details"] = {
            "new_status": event_details.get("status", "active"),
            **event_details
        }
    else:
        return None
    return event


def _append_event_to_chain(chain: Any, event: dict[str, Any]) -> str:
    """Submit an event through the chain's durable ordering service."""
    add_event_method = getattr(chain, "add_event", None)
    if not callable(add_event_method):
        raise RuntimeError("Sub-chain does not support durable event submission")
    event_id = add_event_method(event)
    if not isinstance(event_id, str) or not event_id.strip():
        raise RuntimeError("Sub-chain did not acknowledge the event")
    return event_id


@event_group.command(name="show")
@click.argument('chain_name')
@click.option('--entity-id', help='Filter by entity ID')
@click.pass_context
def show_events(ctx: click.Context, chain_name: str, entity_id: str | None) -> None:
    """Show events in a durably registered sub-chain."""
    try:
        chain = get_sub_chain(ctx, chain_name)
        if not chain:
            raise click.ClickException(f"Sub-chain not found: {chain_name}")
        
        events = _get_events_from_chain(chain, entity_id)
        
        if not events:
            filter_msg = f" for entity {entity_id}" if entity_id else ""
            click.echo(f"No events found in chain {chain_name}{filter_msg}")
            return
        
        click.echo(f"Events in chain {chain_name}:")
        for event in events:
            click.echo(
                f"  - {event.get('event', 'unknown')} | "
                f" Entity: {event.get('entity_id', 'N/A')} | "
                f" Time: {event.get('timestamp', 'N/A')}"
            )
        
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Could not show events: {exc}") from exc


def _get_events_from_chain(chain: Any, entity_id: str | None = None) -> list[dict[str, Any]]:
    """Helper to retrieve and filter events from chain"""
    events = []
    # Safe traversal of attributes
    chain_blocks = getattr(chain, 'chain', [])
    for block in chain_blocks:
        # Handle if block is dict or object
        block_events = block.get(
            'events', []) if isinstance(block, dict) else getattr(block, 'events', [])
        
        for event in block_events:
            # Handle PyArrow or Dict
            # For CLI mock, assume dict
            if isinstance(event, dict) and (
                not entity_id or event.get('entity_id') == entity_id
            ):
                events.append(event)
    return events
