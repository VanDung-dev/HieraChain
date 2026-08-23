"""
Utility helper functions for SubChain rebalancer.
"""

from typing import Any


def _get_sub_chain_id(subchain: Any) -> str:
    if hasattr(subchain, "name"):
        return subchain.name
    if hasattr(subchain, "sub_chain_id"):
        return subchain.sub_chain_id
    return f"subchain-{id(subchain)}"


def _get_event_count(subchain: Any) -> int:
    if hasattr(subchain, "get_event_count"):
        return subchain.get_event_count()
    if hasattr(subchain, "events"):
        return len(subchain.events)
    if hasattr(subchain, "chain"):
        total = 0
        for block in subchain.chain:
            if hasattr(block, "events"):
                total += len(block.events)
        return total
    return 0


def _get_block_count(subchain: Any) -> int:
    if hasattr(subchain, "get_block_count"):
        return subchain.get_block_count()
    if hasattr(subchain, "chain"):
        return len(subchain.chain)
    return 0
