"""
HieraChain CLI Tool (hrc)

This module provides a command-line interface for managing HieraChain networks.
It allows creating chains, adding events, submitting proofs, and viewing chain information.

Each chain can contain events that represent business operations, and sub-chains can submit
cryptographic proofs to the main chain for hierarchical verification.
"""

import click
from typing import cast
from click import Command

from hierachain.cli.verify import verify_group
from hierachain.cli.store import load_chains_from_file
from hierachain.cli.chain import (
    chain_group,
    create as create_chain_cmd,
    list_chains as list_chains_cmd,
    submit_proof as submit_proof_cmd
)
from hierachain.cli.node import (
    node_group,
    start_node,
    init_node
)
from hierachain.cli.event import (
    event_group,
    add_event as add_event_cmd,
    show_events as show_events_cmd
)

@click.group()
@click.option('--config', default='chains.json', help='Configuration file path')
@click.pass_context
def hrc(ctx, config):
    """HieraChain CLI - Simple management tool"""
    ctx.ensure_object(dict)
    ctx.obj['config_file'] = config
    
    # Load existing chains
    load_chains_from_file(config)


# Register sub-commands (Groups)
hrc.add_command(cast(Command, verify_group))
hrc.add_command(cast(Command, node_group))
hrc.add_command(cast(Command, chain_group))
hrc.add_command(cast(Command, event_group))

# Node
hrc.add_command(cast(Command, start_node))
hrc.add_command(cast(Command, init_node))

# Chain
hrc.add_command(cast(Command, create_chain_cmd), name="create_chain")
hrc.add_command(cast(Command, list_chains_cmd), name="list_chains")
hrc.add_command(cast(Command, submit_proof_cmd), name="submit_proof")
hrc.add_command(cast(Command, add_event_cmd), name="add_event")
hrc.add_command(cast(Command, show_events_cmd), name="show_events")

if __name__ == '__main__':
    hrc()