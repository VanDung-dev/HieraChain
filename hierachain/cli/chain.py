"""
Chain management commands.
"""

import click

from hierachain.cli.store import (
    get_all_chains,
    get_main_chain,
    get_sub_chain,
    save_chain_to_memory,
    save_chains_to_file,
)
from hierachain.domains.chains.domain_chain import DomainChain


@click.group()
def chain_group():
    """Chain management commands."""


@chain_group.command()
@click.argument(
    'chain_type',
    type=click.Choice(['supply_chain', 'healthcare', 'finance', 'manufacturing'])
)
@click.option('--name', required=True, help='Chain name')
@click.option('--parent', default='main', help='Parent chain')
@click.pass_context
def create(ctx: click.Context, chain_type, name, parent):
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
def submit_proof(chain_name: str) -> None:
    """Reject submission through the nonpersistent CLI chain registry."""
    raise click.ClickException(
        "CLI proof submission requires a durable HierarchyManager; use the authenticated API"
    )


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
