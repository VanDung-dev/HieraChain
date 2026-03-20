"""
API endpoints for HieraChain Ledger

This module provides RESTful API endpoints for interacting with the HieraChain system.
The system follows a two-level architecture where sub-chains handle business events
and the main chain stores cryptographic proofs from sub-chains.
"""

import time
import re
import os
from typing import Any
from fastapi import (
    APIRouter, HTTPException, status, Depends, BackgroundTasks
)
from fastapi.responses import JSONResponse

from hierachain.security.sanitization import (
    sanitize_string, sanitize_dict
)
from hierachain.security.secure_logging import SecureLogger
from hierachain.api.storage.endpoint_helpers import (
    is_ipfs_enabled,
    process_event_details,
    resolve_multiple_events
)
from hierachain.api.storage import IPFSError

from hierachain.api.v1.schemas import (
    EventRequest,
    EventResponse,
    ChainInfoResponse,
    ProofSubmissionResponse,
    EntityTraceResponse,
    ChainStatsResponse
)
from hierachain.core.blockchain import Blockchain
from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.sub_chain import SubChain
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.domains.generic.utils.entity_tracer import EntityTracer
from hierachain.security.verify.api_key_verifier import (
    require_event_access,
    require_chain_access,
    require_proof_access
)

# Secure logger for API v1
api_logger = SecureLogger("hierachain.api.v1")

router = APIRouter(prefix="/api/v1", tags=["HieraChain"])

# Dependency Injection using Lazy Getter Pattern
_hierarchy_manager: HierarchyManager | None = None
_entity_tracer: EntityTracer | None = None


def get_hierarchy_manager() -> HierarchyManager:
    """Lazy getter for HierarchyManager singleton"""
    global _hierarchy_manager
    if _hierarchy_manager is None:
        _hierarchy_manager = HierarchyManager()
    return _hierarchy_manager


def get_entity_tracer(
    manager: HierarchyManager = Depends(get_hierarchy_manager)
) -> EntityTracer:
    """Lazy getter for EntityTracer singleton"""
    global _entity_tracer
    if _entity_tracer is None:
        _entity_tracer = EntityTracer(manager)
    return _entity_tracer


def reset_instances() -> None:
    """Reset global instances (for testing purpose)"""
    global _hierarchy_manager, _entity_tracer
    _hierarchy_manager = None
    _entity_tracer = None


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}


@router.get(
    "/chains",
    response_model=list[ChainInfoResponse],
    dependencies=[Depends(require_chain_access)]
)
async def list_chains(manager: HierarchyManager = Depends(get_hierarchy_manager)):
    """List all chains in the hierarchy"""
    try:
        chains = []
        
        # Add main chain info
        main_chain = manager.get_main_chain()
        if main_chain:
            chains.append(ChainInfoResponse(
                name="main_chain",
                type="main",
                block_count=len(getattr(main_chain, 'chain', [])),
                latest_block_hash=(
                    main_chain.get_latest_block().hash
                    if getattr(main_chain, 'chain', None) else None
                )
            ))
        
        # Add sub-chains info
        for sub_chain_name, sub_chain in manager.get_all_sub_chains().items():
            chains.append(ChainInfoResponse(
                name=sub_chain_name,
                type="sub",
                block_count=len(getattr(sub_chain, 'chain', [])),
                latest_block_hash=(
                    sub_chain.get_latest_block().hash
                    if getattr(sub_chain, 'chain', None) else None
                )
            ))
        
        return chains
    except Exception as e:
        api_logger.error("Failed to list chains", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to list chains. An internal error has occurred."
        ) from e


@router.post(
    "/chains/{chain_name}/events",
    response_model=EventResponse,
    dependencies=[Depends(require_event_access)]
)
async def add_event(
    chain_name: str,
    event_request: EventRequest,
    background_tasks: BackgroundTasks,
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    """
    Add an event to a specific sub-chain.

    Supports both on-chain and off-chain (IPFS) data storage:
    - On-chain: Provide 'details' dict in request
    - Off-chain: Provide 'details_cid' and 'details_nonce' in request

    If IPFS is enabled and large details are provided, they can be stored off-chain
    to reduce block size and improve performance.
    """
    try:
        sub_chain = manager.get_sub_chain(chain_name)
        if not sub_chain:
            raise HTTPException(
                status_code=404, detail=f"Sub-chain '{chain_name}' not found"
            )

        # Sanitize user input before storing
        safe_entity_id = sanitize_string(event_request.entity_id)
        safe_event_type = sanitize_string(event_request.event_type)

        # Process event details - handle both on-chain and off-chain data
        inline_details, cid_info = process_event_details(
            event_request,
            background_tasks=background_tasks
        )

        # Sanitize inline details if provided
        if inline_details:
            safe_details = sanitize_dict(inline_details)
        else:
            safe_details = None

        # Create event from request
        event = {
            "entity_id": safe_entity_id,
            "event": safe_event_type,
            "timestamp": time.time(),
        }

        # Add details based on storage type
        if cid_info:
            # Off-chain storage (IPFS)
            event["details_cid"] = cid_info["cid"]
            event["details_nonce"] = cid_info["nonce"]
            if cid_info.get("metadata"):
                event["details_metadata"] = cid_info["metadata"]

            api_logger.info(
                "Event using off-chain storage",
                chain_name=chain_name,
                cid=cid_info["cid"],
                entity_id=safe_entity_id
            )
        else:
            # On-chain storage (traditional)
            event["details"] = safe_details or {}

        # Add event to sub-chain
        sub_chain.add_event(event)

        api_logger.audit(
            action="add_event",
            resource="sub_chain",
            success=True,
            chain_name=chain_name,
            entity_id=safe_entity_id,
            storage_type="offchain" if cid_info else "onchain"
        )

        return EventResponse(
            success=True,
            message=f"Event added to chain '{chain_name}'" + (
                " (off-chain storage)" if cid_info else ""
            ),
            event_id=(
                f"{chain_name}_{len(sub_chain.chain)}_{len(sub_chain.pending_events)}"
            )
        )
    except IPFSError as e:
        api_logger.error(
            "IPFS error while adding event",
            error=str(e),
            chain_name=chain_name
        )
        raise HTTPException(
            status_code=503,
            detail=f"IPFS storage error: {str(e)}"
        ) from e
    except Exception as e:
        api_logger.error("Failed to add event", error=str(e), chain_name=chain_name)
        raise HTTPException(
            status_code=500,
            detail="Failed to add event. An internal error has occurred."
        ) from e


@router.post(
    "/chains/{chain_name}/submit-proof",
    response_model=ProofSubmissionResponse,
    dependencies=[Depends(require_proof_access)]
)
async def submit_proof(
    chain_name: str, manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    """Submit proof from sub-chain to main chain"""
    try:
        sub_chain = manager.get_sub_chain(chain_name)
        if not sub_chain:
            raise HTTPException(
                status_code=404, detail=f"Sub-chain '{chain_name}' not found"
            )
        
        main_chain = manager.get_main_chain()
        if not main_chain:
            raise HTTPException(
                status_code=500, detail="Main chain not available"
            )
        
        # Submit proof with custom metadata if provided
        metadata_filter = None
        
        # Check if sub_chain has the required method
        if hasattr(sub_chain, 'submit_proof_to_main'):
            success = sub_chain.submit_proof_to_main(main_chain, metadata_filter)
        else:
            # Try alternative method
            success = main_chain.add_proof(
                sub_chain_name=sub_chain.name,
                proof_hash="mock_proof_hash",
                metadata={
                    "proof": "mock_proof",
                    "timestamp": time.time()
                }
            )
        
        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to submit proof to main chain"
            )
        
        return ProofSubmissionResponse(
            success=True,
            message=f"Proof submitted from '{chain_name}' to main chain",
            proof_id=f"{chain_name}_{len(sub_chain.chain)}" if sub_chain.chain else None
        )
    except Exception as e:
        api_logger.error("Failed to submit proof", error=str(e), chain_name=chain_name)
        raise HTTPException(
            status_code=500,
            detail="Failed to submit proof. An internal error has occurred."
        ) from e


@router.get(
    "/entities/{entity_id}/trace",
    response_model=EntityTraceResponse,
    dependencies=[Depends(require_chain_access)]
)
async def trace_entity(
    entity_id: str,
    chain_name: str | None = None,
    resolve_cid: bool = False,
    manager: HierarchyManager = Depends(get_hierarchy_manager),
    tracer: EntityTracer = Depends(get_entity_tracer)
):
    """
    Trace an entity across chains.

    Args:
        entity_id: Unique identifier of the entity to trace
        chain_name: Optional chain name to limit trace to specific chain
        resolve_cid: If True, resolve IPFS CIDs to actual event details (default: False)

    Returns:
        Entity trace with events across chains

    Note:
        When resolve_cid=True, event details stored in IPFS will be downloaded
        and decrypted automatically. This is useful for complete entity history
        but may increase response time.
    """
    # Sanitize path parameter
    safe_entity_id = sanitize_string(entity_id)

    try:
        if chain_name:
            # Trace in specific chain
            sub_chain = manager.get_sub_chain(chain_name)
            if not sub_chain:
                raise HTTPException(
                    status_code=404, detail=f"Sub-chain '{chain_name}' not found"
                )

            trace_result = tracer.trace_entity_in_chain(safe_entity_id, chain_name)
            events = trace_result.get("events", [])
        else:
            # Trace across all chains
            trace_result = tracer.trace_entity_across_chains(safe_entity_id)
            # Flatten events from all chains
            events = []
            for chain_events in trace_result.values():
                events.extend(chain_events)

        # Resolve CIDs if requested and IPFS is enabled
        if resolve_cid and is_ipfs_enabled():
            events = await resolve_multiple_events(events, resolve=True)

        # Extract chain names from the events
        chain_names = list(set(event.get('chain', 'unknown') for event in events))

        return EntityTraceResponse(
            entity_id=safe_entity_id,
            chains=chain_names,
            events=events
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            "Failed to trace entity", error=str(e), entity_id=safe_entity_id
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to trace entity. An internal error has occurred."
        ) from e


def _get_chain_by_name(manager: HierarchyManager, chain_name: str) -> Blockchain | None:
    """Helper to get main or sub chain by name"""
    if chain_name == "main_chain":
        return manager.get_main_chain()
    return manager.get_sub_chain(chain_name)


def _calculate_basic_chain_stats(chain) -> tuple[int, int]:
    """Calculate basic block and event counts for a chain"""
    chain_blocks = getattr(chain, 'chain', [])
    total_blocks = len(chain_blocks)
    
    # Calculate total events across all blocks
    total_events = sum(len(getattr(block, 'events', [])) for block in chain_blocks)
        
    return total_blocks, total_events


def _get_extended_chain_stats(
    manager: HierarchyManager,
    chain_name: str,
    total_blocks: int
) -> tuple[int | None, int | None]:
    """Get additional statistics based on the chain type"""
    if chain_name == "main_chain":
        # For main chain, provide proof count (blocks excluding genesis)
        proof_count = max(0, total_blocks - 1)
        # Count registered sub-chains
        registered_sub_chains = len(manager.get_all_sub_chains())
        return proof_count, registered_sub_chains
    
    return None, None


@router.get(
    "/chains/{chain_name}/stats",
    response_model=ChainStatsResponse,
    dependencies=[Depends(require_chain_access)]
)
async def get_chain_stats(
    chain_name: str,
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    """Get statistics for a specific chain"""
    try:
        chain = _get_chain_by_name(manager, chain_name)
        if not chain:
            raise HTTPException(
                status_code=404, detail=f"Chain '{chain_name}' not found"
            )
        
        total_blocks, total_events = _calculate_basic_chain_stats(chain)
        metrics = _get_extended_chain_stats(manager, chain_name, total_blocks)
        proof_count, registered_sub_chains = metrics
        
        return ChainStatsResponse(
            chain_name=chain_name,
            total_blocks=total_blocks,
            total_events=total_events,
            proof_count=proof_count,
            registered_sub_chains=registered_sub_chains
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            "Failed to get chain stats", error=str(e), chain_name=chain_name
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get chain stats. An internal error has occurred."
        ) from e


def _get_block_events_data(block: Any) -> list[dict[str, Any]]:
    """Safe extraction of event data from a block"""
    if hasattr(block, 'to_event_list'):
        # Best way: uses internal serialization
        return block.to_event_list()

    events_data = getattr(block, 'events', [])
    if hasattr(events_data, 'to_pylist'):
        # Fallback for Arrow Table
        return events_data.to_pylist()

    return events_data if isinstance(events_data, list) else []


def _serialize_block(block: Any) -> dict[str, Any]:
    """Serialize a single block for API response"""
    events_data = _get_block_events_data(block)
    return {
        "index": getattr(block, 'index', None),
        "hash": getattr(block, 'hash', None),
        "previous_hash": getattr(block, 'previous_hash', None),
        "timestamp": getattr(block, 'timestamp', None),
        "events_count": len(events_data),
        "events": events_data
    }


@router.post(
    "/chains/{chain_name}/create", dependencies=[Depends(require_chain_access)]
)
async def create_sub_chain(
    chain_name: str,
    chain_type: str = "generic",
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    """Create a new sub-chain"""
    if not re.match(r'^[a-zA-Z0-9_\-]+$', chain_name):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid chain identifier '{sanitize_string(chain_name)}'. "
                "Only alphanumeric, underscore, and hyphen are allowed."
            )
        )
    # Sanitize chain_type parameter
    safe_chain_type = sanitize_string(chain_type)

    try:
        main_chain = manager.get_main_chain()
        if not main_chain:
            # Create main chain if it doesn't exist
            main_chain = MainChain()
            manager.set_main_chain(main_chain)

        safe_chain_name = os.path.basename(chain_name)

        # Create sub-chain
        sub_chain = SubChain(name=safe_chain_name, domain_type=safe_chain_type)
        manager.add_sub_chain(safe_chain_name, sub_chain)

        api_logger.audit(
            action="create",
            resource="sub_chain",
            success=True,
            chain_name=safe_chain_name,
            chain_type=safe_chain_type,
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "message": f"Sub-chain '{chain_name}' created successfully",
                "chain_name": chain_name
            }
        )
    except Exception as e:
        api_logger.error(
            "Failed to create sub-chain", error=str(e), chain_name=chain_name
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create sub-chain. An internal error has occurred."
        ) from e


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
    """
    Get blocks from a specific chain.

    Args:
        chain_name: Name of the chain
        limit: Maximum number of blocks to return (default: 10)
        offset: Offset for pagination (default: 0)
        resolve_cid: If True, resolve IPFS CIDs to actual data (default: False)

    Returns:
        Block data with optional CID resolution

    Note:
        When resolve_cid=True, event details stored in IPFS will be downloaded
        and decrypted automatically. This may increase response time for blocks
        with many off-chain events.
    """
    try:
        chain = _get_chain_by_name(manager, chain_name)
        if not chain:
            raise HTTPException(
                status_code=404, detail=f"Chain '{chain_name}' not found"
            )

        # Get blocks with pagination
        chain_blocks = getattr(chain, 'chain', [])
        blocks = chain_blocks[offset:offset + limit]

        # Serialize each block using helper
        block_data = [_serialize_block(block) for block in blocks]

        # Resolve CIDs if requested and IPFS is enabled
        if resolve_cid and is_ipfs_enabled():
            for block in block_data:
                if 'events' in block:
                    # Resolve CIDs for all events in the block
                    block['events'] = await resolve_multiple_events(
                        block['events'],
                        resolve=True
                    )

        return {
            "chain_name": chain_name,
            "blocks": block_data,
            "total_blocks": len(chain_blocks),
            "offset": offset,
            "limit": limit,
            "resolved": resolve_cid and is_ipfs_enabled()
        }
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error("Failed to get blocks", error=str(e), chain_name=chain_name)
        raise HTTPException(
            status_code=500,
            detail="Failed to get blocks. An internal error has occurred."
        ) from e
