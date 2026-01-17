"""
Chain management commands.
"""

import click
import time

from hierachain.cli.store import (
    get_main_chain, get_sub_chain, save_chain_to_memory, 
    save_chains_to_file, get_all_chains
)

# Need to import classes for instantiation
try:
    from hierachain.hierarchical.main_chain import MainChain
    from hierachain.hierarchical.sub_chain import SubChain
    from hierachain.domains.generic.chains.domain_chain import DomainChain
except ImportError:
    # Fallback if framework not fully installed/available
    class MainChain: pass
    class SubChain: pass
    class DomainChain:
        def __init__(self, name, parent):
            self.name = name
            self.parent = parent
            self.chain = []

@click.group()
def chain_group():
    """Chain management commands."""
    pass

@chain_group.command()
@click.argument(
    'chain_type', type=click.Choice(['supply_chain', 'healthcare', 'finance', 'manufacturing'])
)
@click.option('--name', required=True, help='Chain name')
@click.option('--parent', default='main', help='Parent chain')
@click.pass_context
def create(ctx, chain_type, name, parent):
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
        # For CLI prototype, we use DomainChain for all, setting the type attribute
        chain = DomainChain(name, parent_chain)
        chain.domain_type = chain_type
        
        # Store chain
        save_chain_to_memory(chain)
        
        # Save to file
        config_file = ctx.obj.get('config_file', 'chains.json')
        save_chains_to_file(config_file)
        
        click.echo(f"Successfully created {chain_type} chain '{name}'")
        
    except Exception as e:
        click.echo(f"Error creating chain: {e}")

@chain_group.command()
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
        # We assume chain has submit_proof_to_main (if it's a real class)
        # If it's a placeholder, this might fail, so we wrap in try
        if hasattr(chain, 'submit_proof_to_main'):
            chain.submit_proof_to_main(main_chain, metadata_filter=lambda c: {
                "chain_name": c.name,
                "domain_type": getattr(c, 'domain_type', 'generic'),
                "block_count": len(getattr(c, 'chain', [])),
                "timestamp": time.time()
            })
            click.echo(f"Successfully submitted proof from chain '{chain_name}' to main chain")
        else:
            click.echo(f"Chain object does not support proof submission (Mock Mode)")
        
        # Save to file
        save_chains_to_file('chains.json')
        
    except Exception as e:
        click.echo(f"Error submitting proof: {e}")

@chain_group.command(name="list")
def list_chains():
    """List all chains"""
    try:
        chains = get_all_chains()
        if not chains:
            click.echo("No chains found")
            return
        
        click.echo("Available chains:")
        for name, chain in chains.items():
            domain_type = getattr(chain, 'domain_type', 'generic')
            block_count = len(getattr(chain, 'chain', []))
            click.echo(f"  - {name} ({domain_type}) - {block_count} blocks")
        
    except Exception as e:
        click.echo(f"Error listing chains: {e}")
