"""
Event management commands.
"""

import click
import time
import json

from hierachain.cli.store import get_sub_chain, save_chains_to_file


@click.group()
def event_group():
    """Event management commands."""
    pass


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
def add_event(ctx: click.Context, chain_name, event_type, entity_id, details):
    """Add event to chain"""
    try:
        chain = get_sub_chain(chain_name)
        if not chain:
            click.echo(f"Chain not found: {chain_name}")
            return
        
        # Parse additional details
        event_details = {}
        if details:
            try:
                event_details = json.loads(details)
            except json.JSONDecodeError:
                click.echo("Invalid JSON format for details")
                return
        
        # Create event based on type
        event = _create_event_payload(event_type, entity_id, event_details)
        if not event:
            click.echo(f"Unknown event type: {event_type}")
            return
            
        # Add event to chain
        _append_event_to_chain(chain, event)
        
        # Save to file
        config_file = ctx.obj.get('config_file', 'chains.json')
        save_chains_to_file(config_file)
        
        click.echo(
            f"Added '{event_type}' event for entity {entity_id} to chain {chain_name}"
            )
        
    except Exception as e:
        click.echo(f"Error adding event: {e}")


def _create_event_payload(event_type, entity_id, event_details):
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


def _append_event_to_chain(chain, event) -> None:
    """Helper to append event to chain object"""
    if hasattr(chain, 'add_event'):
        chain.add_event(event)
    elif hasattr(chain, 'chain') and isinstance(chain.chain, list):
        # Mock behavior if it's a simple object
        if not chain.chain:
            # Create a mock block
            chain.chain.append(type('Block', (), {'events': []})())

        # Append to last block
        block = chain.chain[-1]
        if hasattr(block, 'events'):
            block.events.append(event)


@event_group.command(name="show")
@click.argument('chain_name')
@click.option('--entity-id', help='Filter by entity ID')
def show_events(chain_name, entity_id):
    """Show events in chain"""
    try:
        chain = get_sub_chain(chain_name)
        if not chain:
            click.echo(f"Chain not found: {chain_name}")
            return
        
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
        
    except Exception as e:
        click.echo(f"Error showing events: {e}")


def _get_events_from_chain(chain, entity_id=None):
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
            if not entity_id or event.get('entity_id') == entity_id:
                events.append(event)
    return events
