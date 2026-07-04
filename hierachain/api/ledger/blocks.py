"""API Ledger — block retrieval endpoints.

Pagination and detail lookup for blocks across chains,
with optional IPFS CID resolution.
"""

from typing import Any
from fastapi import APIRouter, HTTPException, status, Depends

from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.api.ledger.chains import get_chain_by_name
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.api.storage.endpoint_helpers import (
    is_ipfs_enabled,
    resolve_multiple_events,
)
from hierachain.core.utils import get_block_events as _get_block_events_data

router = APIRouter(tags=["HieraChain"])


def _serialize_block(block: Any) -> dict[str, Any]:
    events_data = _get_block_events_data(block)
    return {
        "index": getattr(block, 'index', None),
        "hash": getattr(block, 'hash', None),
        "previous_hash": getattr(block, 'previous_hash', None),
        "timestamp": getattr(block, 'timestamp', None),
        "events_count": len(events_data),
        "events": events_data
    }


def _validate_chain_exists_for_blocks(
    manager: HierarchyManager,
    chain_name: str
) -> Any:
    chain = get_chain_by_name(manager, chain_name)
    if not chain:
        raise HTTPException(
            status_code=404, detail=f"Chain '{chain_name}' not found"
        )
    return chain


def _extract_paginated_blocks(
    chain: Any,
    offset: int,
    limit: int
) -> list:
    chain_blocks = getattr(chain, 'chain', [])
    return chain_blocks[offset:offset + limit]


async def _resolve_blocks_cids(
    block_data: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not is_ipfs_enabled():
        return block_data

    for block in block_data:
        if 'events' in block:
            block['events'] = await resolve_multiple_events(
                block['events'],
                resolve=True
            )
    return block_data


@router.get(
    "/chains/{chain_name}/blocks", dependencies=[Depends(require_chain_access)]
)
async def get_chain_blocks(
    chain_name: str,
    limit: int = 10,
    offset: int = 0,
    resolve_cid: bool = False,
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    chain = _validate_chain_exists_for_blocks(manager, chain_name)
    chain_blocks = getattr(chain, 'chain', [])
    blocks = _extract_paginated_blocks(chain, offset, limit)
    block_data = [_serialize_block(block) for block in blocks]

    if resolve_cid:
        block_data = await _resolve_blocks_cids(block_data)

    return {
        "chain_name": chain_name,
        "blocks": block_data,
        "total_blocks": len(chain_blocks),
        "offset": offset,
        "limit": limit,
        "resolved": resolve_cid and is_ipfs_enabled()
    }


def _find_block(chain_blocks: list[Any], index_or_hash: str) -> Any | None:
    """Finds a block in chain_blocks by integer index or hash string."""
    if index_or_hash.isdigit():
        idx = int(index_or_hash)
        if 0 <= idx < len(chain_blocks):
            return chain_blocks[idx]

    for block in chain_blocks:
        if getattr(block, 'hash', '') == index_or_hash:
            return block
    return None


@router.get(
    "/chains/{chain_name}/blocks/{index_or_hash}",
    dependencies=[Depends(require_chain_access)]
)
async def get_block_detail(
    chain_name: str,
    index_or_hash: str,
    resolve_cid: bool = False,
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    chain = _validate_chain_exists_for_blocks(manager, chain_name)
    chain_blocks = getattr(chain, 'chain', [])

    target_block = _find_block(chain_blocks, index_or_hash)

    if not target_block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block '{index_or_hash}' not found in chain '{chain_name}'"
        )

    block_data = _serialize_block(target_block)

    if resolve_cid and is_ipfs_enabled():
        resolved_blocks = await _resolve_blocks_cids([block_data])
        block_data = resolved_blocks[0]

    return block_data
