"""
Node management commands.
"""

import orjson
import os
import time
import click

from hierachain.hierarchical.main_chain import MainChain


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


def save_chain_to_memory(chain):
    """Save chain to in-memory storage"""
    _chains_storage[chain.name] = chain


def get_all_chains():
    """Return all chains in storage"""
    return _chains_storage


def load_chains_from_file(filepath: str) -> bool:
    """Load chains from JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r'):
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
        with open(filepath, 'wb') as f:
            f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
        return True
    except Exception as e:
        click.echo(f"Error saving chains: {e}")
    return False
