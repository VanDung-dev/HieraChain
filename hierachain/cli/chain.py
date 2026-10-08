"""
Chain management commands.
"""

import click

from hierachain.cli.store import get_all_chains, get_hierarchy_manager


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
def create(ctx: click.Context, chain_type: str, name: str, parent: str) -> None:
    """Create a durable sub-chain attached to the main chain."""
    if parent != "main":
        raise click.ClickException(
            "Nested parent chains are unsupported; --parent must be 'main'"
        )

    try:
        manager = get_hierarchy_manager(ctx)
        if manager.get_sub_chain(name) is not None:
            raise click.ClickException(f"Sub-chain already exists: {name}")
        if manager.create_sub_chain(name, chain_type) is not True:
            raise click.ClickException(f"Could not create sub-chain: {name}")
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Could not create sub-chain {name}: {exc}") from exc

    click.echo(f"Successfully created {chain_type} sub-chain '{name}'")


@chain_group.command()
@click.argument('chain_name')
def submit_proof(chain_name: str) -> None:
    """Reject submission through the nonpersistent CLI chain registry."""
    raise click.ClickException(
        "CLI proof submission requires a durable HierarchyManager; use the authenticated API"
    )


@chain_group.command(name="list")
@click.pass_context
def list_chains(ctx: click.Context) -> None:
    """List all registered sub-chains from durable storage."""
    try:
        chains = get_all_chains(ctx)
        if not chains:
            click.echo("No sub-chains found")
            return
        
        click.echo("Available sub-chains:")
        for name, chain in chains.items():
            domain_type = getattr(chain, 'domain_type', 'generic')
            block_count = len(getattr(chain, 'chain', []))
            click.echo(f"  - {name} ({domain_type}) - {block_count} blocks")
        
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Could not list sub-chains: {exc}") from exc
