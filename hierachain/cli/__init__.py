"""
HieraChain CLI Tool (hrc)

This module provides a command-line interface for managing HieraChain networks.
It allows creating chains, adding events, submitting proofs, and viewing chain information.

Each chain can contain events that represent business operations, and sub-chains can submit
cryptographic proofs to the main chain for hierarchical verification.
"""

import click
import time
import json
import os

# Import framework components
try:
    from hierachain.hierarchical.main_chain import MainChain
    from hierachain.hierarchical.sub_chain import SubChain
    from hierachain.domains.generic.chains.domain_chain import DomainChain
except ImportError:
    # Placeholder classes for when the full framework isn't available
    class MainChain:
        pass
    class SubChain:
        pass
    class DomainChain:
        pass


# Storage for chains (in production, this would be persistent)
_chains_storage = {}
_main_chain = None


def get_main_chain():
    """Get or create main chain"""
    global _main_chain
    if _main_chain is None:
        _main_chain = MainChain()
    return _main_chain


def get_sub_chain(name: str):
    """Get sub-chain by name"""
    return _chains_storage.get(name)


def save_chain(chain):
    """Save chain to storage"""
    _chains_storage[chain.name] = chain


def load_chains_from_file(filepath: str) -> bool:
    """Load chains from JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                _data = json.load(f)
                # In a real implementation, this would deserialize the chains
                return True
    except Exception as e:
        click.echo(f"Error loading chains: {e}")
    return False


def save_chains_to_file(filepath: str) -> bool:
    """Save chains to JSON file"""
    try:
        data = {
            "chains": list(_chains_storage.keys()),
            "timestamp": time.time()
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        click.echo(f"Error saving chains: {e}")
    return False


@click.group()
@click.option('--config', default='chains.json', help='Configuration file path')
@click.pass_context
def hrc(ctx, config):
    """HieraChain CLI - Simple management tool"""
    ctx.ensure_object(dict)
    ctx.obj['config_file'] = config
    
    # Load existing chains
    load_chains_from_file(config)


@hrc.command()
@click.argument('chain_type', type=click.Choice(['supply_chain', 'healthcare', 'finance', 'manufacturing']))
@click.option('--name', required=True, help='Chain name')
@click.option('--parent', default='main', help='Parent chain')
@click.pass_context
def create_chain(ctx, chain_type, name, parent):
    """Create new chain"""
    try:
        # Get parent chain
        if parent == 'main':
            parent_chain = get_main_chain()
        else:
            parent_chain = get_sub_chain(parent)
            if not parent_chain:
                click.echo(f"Parent chain not found: {parent}")
                return
        
        # Create chain based on type
        if chain_type == 'supply_chain':
            chain = DomainChain(name, parent_chain)
            chain.domain_type = 'supply_chain'
        elif chain_type == 'healthcare':
            chain = DomainChain(name, parent_chain)
            chain.domain_type = 'healthcare'
        elif chain_type == 'finance':
            chain = DomainChain(name, parent_chain)
            chain.domain_type = 'finance'
        else:  # manufacturing
            chain = DomainChain(name, parent_chain)
            chain.domain_type = 'manufacturing'
        
        # Store chain
        save_chain(chain)
        
        # Save to file
        save_chains_to_file(ctx.obj['config_file'])
        
        click.echo(f"Successfully created {chain_type} chain '{name}'")
        
    except Exception as e:
        click.echo(f"Error creating chain: {e}")


@hrc.command()
@click.argument('chain_name')
@click.argument('event_type', type=click.Choice(['start_operation', 'complete_operation', 'quality_check', 'status_change']))
@click.option('--entity-id', required=True, help='Entity ID')
@click.option('--details', help='Additional details as JSON string')
@click.pass_context
def add_event(ctx, chain_name, event_type, entity_id, details):
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
        if event_type == 'start_operation':
            # Generate deterministic resource ID based on entity_id hash
            resource_id = 1 + (hash(entity_id) % 10)  # Range 1-10
            
            event = {
                "entity_id": entity_id,
                "event": "operation_start",
                "timestamp": time.time(),
                "details": {
                    "resource": f"RESOURCE-{resource_id}",
                    **event_details
                }
            }
        elif event_type == 'complete_operation':
            event = {
                "entity_id": entity_id,
                "event": "operation_complete",
                "timestamp": time.time(),
                "details": event_details
            }
        elif event_type == 'quality_check':
            event = {
                "entity_id": entity_id,
                "event": "quality_check",
                "timestamp": time.time(),
                "details": {
                    "result": event_details.get("result", "pass"),
                    **event_details
                }
            }
        elif event_type == 'status_change':
            event = {
                "entity_id": entity_id,
                "event": "status_change",
                "timestamp": time.time(),
                "details": {
                    "new_status": event_details.get("status", "active"),
                    **event_details
                }
            }
        else:
            click.echo(f"Unknown event type: {event_type}")
            return
        
        # Add event to chain
        chain.add_event(event)
        
        # Save to file
        save_chains_to_file(ctx.obj['config_file'])
        
        click.echo(f"Added '{event_type}' event for entity {entity_id} to chain {chain_name}")
        
    except Exception as e:
        click.echo(f"Error adding event: {e}")


@hrc.command()
@click.argument('chain_name')
def submit_proof(chain_name):
    """Submit proof from sub-chain to main chain"""
    try:
        chain = get_sub_chain(chain_name)
        if not chain:
            click.echo(f"Chain not found: {chain_name}")
            return
        
        main_chain = get_main_chain()
        
        # Submit proof with metadata
        chain.submit_proof_to_main(main_chain, metadata_filter=lambda c: {
            "chain_name": c.name,
            "domain_type": getattr(c, 'domain_type', 'generic'),
            "block_count": len(c.chain),
            "timestamp": time.time()
        })
        
        # Save to file
        save_chains_to_file('chains.json')
        
        click.echo(f"Successfully submitted proof from chain '{chain_name}' to main chain")
        
    except Exception as e:
        click.echo(f"Error submitting proof: {e}")


@hrc.command()
def list_chains():
    """List all chains"""
    try:
        if not _chains_storage:
            click.echo("No chains found")
            return
        
        click.echo("Available chains:")
        for name, chain in _chains_storage.items():
            domain_type = getattr(chain, 'domain_type', 'generic')
            block_count = len(getattr(chain, 'chain', []))
            click.echo(f"  - {name} ({domain_type}) - {block_count} blocks")
        
    except Exception as e:
        click.echo(f"Error listing chains: {e}")


@hrc.command()
@click.argument('chain_name')
@click.option('--entity-id', help='Filter by entity ID')
def show_events(chain_name, entity_id):
    """Show events in chain"""
    try:
        chain = get_sub_chain(chain_name)
        if not chain:
            click.echo(f"Chain not found: {chain_name}")
            return
        
        events = []
        for block in getattr(chain, 'chain', []):
            for event in getattr(block, 'events', []):
                if not entity_id or event.get('entity_id') == entity_id:
                    events.append(event)
        
        if not events:
            filter_msg = f" for entity {entity_id}" if entity_id else ""
            click.echo(f"No events found in chain {chain_name}{filter_msg}")
            return
        
        click.echo(f"Events in chain {chain_name}:")
        for event in events:
            click.echo(f"  - {event.get('event', 'unknown')} | Entity: {event.get('entity_id', 'N/A')} | Time: {event.get('timestamp', 'N/A')}")
        
    except Exception as e:
        click.echo(f"Error showing events: {e}")


if __name__ == '__main__':
    hrc()