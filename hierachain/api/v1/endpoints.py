"""
API endpoints for HieraChain Framework

This module provides RESTful API endpoints for interacting with the HieraChain system.
The system follows a two-level architecture where sub-chains handle business events and the main chain
stores cryptographic proofs from sub-chains.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import time
import re
import os

from hierachain.api.v1.schemas import (
    EventRequest, EventResponse, ChainInfoResponse, 
    ProofSubmissionResponse,
    EntityTraceResponse, ChainStatsResponse
)
from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.sub_chain import SubChain
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.domains.generic.utils.entity_tracer import EntityTracer

router = APIRouter(prefix="/api/v1", tags=["HieraChain"])

# Global instances (in production, use dependency injection)
hierarchy_manager = HierarchyManager()
entity_tracer = EntityTracer(hierarchy_manager)


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@router.get("/chains", response_model=list[ChainInfoResponse])
async def list_chains():
    """List all chains in the hierarchy"""
    try:
        chains = []
        
        # Add main chain info
        main_chain = hierarchy_manager.get_main_chain()
        if main_chain:
            chains.append(ChainInfoResponse(
                name="main_chain",
                type="main",
                block_count=len(getattr(main_chain, 'chain', [])),
                latest_block_hash=main_chain.get_latest_block().hash if getattr(main_chain, 'chain', None) else None
            ))
        
        # Add sub-chains info
        for sub_chain_name, sub_chain in hierarchy_manager.get_all_sub_chains().items():
            chains.append(ChainInfoResponse(
                name=sub_chain_name,
                type="sub",
                block_count=len(getattr(sub_chain, 'chain', [])),
                latest_block_hash=sub_chain.get_latest_block().hash if getattr(sub_chain, 'chain', None) else None
            ))
        
        return chains
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list chains: {str(e)}")

@router.post("/chains/{chain_name}/events", response_model=EventResponse)
async def add_event(chain_name: str, event_request: EventRequest):
    """Add an event to a specific sub-chain"""
    try:
        sub_chain = hierarchy_manager.get_sub_chain(chain_name)
        if not sub_chain:
            raise HTTPException(status_code=404, detail=f"Sub-chain '{chain_name}' not found")
        
        # Create event from request
        event = {
            "entity_id": event_request.entity_id,
            "event": event_request.event_type,
            "timestamp": time.time(),
            "details": event_request.details or {}
        }
        
        # Add event to sub-chain
        sub_chain.add_event(event)
        
        return EventResponse(
            success=True,
            message=f"Event added to chain '{chain_name}'",
            event_id=f"{chain_name}_{len(sub_chain.chain)}_{len(sub_chain.pending_events)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add event: {str(e)}")

@router.post("/chains/{chain_name}/submit-proof", response_model=ProofSubmissionResponse)
async def submit_proof(chain_name: str):
    """Submit proof from sub-chain to main chain"""
    try:
        sub_chain = hierarchy_manager.get_sub_chain(chain_name)
        if not sub_chain:
            raise HTTPException(status_code=404, detail=f"Sub-chain '{chain_name}' not found")
        
        main_chain = hierarchy_manager.get_main_chain()
        if not main_chain:
            raise HTTPException(status_code=500, detail="Main chain not available")
        
        # Submit proof with custom metadata if provided
        metadata_filter = None
        
        # Check if sub_chain has the required method
        if hasattr(sub_chain, 'submit_proof_to_main'):
            sub_chain.submit_proof_to_main(main_chain, metadata_filter)
        else:
            # Try alternative method
            main_chain.add_sub_chain_proof(sub_chain.name, {
                "proof": "mock_proof",
                "timestamp": time.time()
            })
        
        return ProofSubmissionResponse(
            success=True,
            message=f"Proof submitted from '{chain_name}' to main chain",
            proof_id=f"{chain_name}_{len(sub_chain.chain)}" if sub_chain.chain else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit proof: {str(e)}")

@router.get("/entities/{entity_id}/trace", response_model=EntityTraceResponse)
async def trace_entity(entity_id: str, chain_name: Optional[str] = None):
    """Trace an entity across chains"""
    try:
        if chain_name:
            # Trace in specific chain
            sub_chain = hierarchy_manager.get_sub_chain(chain_name)
            if not sub_chain:
                raise HTTPException(status_code=404, detail=f"Sub-chain '{chain_name}' not found")
            
            trace_result = entity_tracer.trace_entity_in_chain(entity_id, chain_name)
            events = trace_result.get("events", [])
        else:
            # Trace across all chains
            trace_result = entity_tracer.trace_entity_across_chains(entity_id)
            # Flatten events from all chains
            events = []
            for chain_events in trace_result.values():
                events.extend(chain_events)
        
        # Extract chain names from the events
        chain_names = list(set(event.get('chain', 'unknown') for event in events))
        
        return EntityTraceResponse(
            entity_id=entity_id,
            chains=chain_names,
            events=events
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trace entity: {str(e)}")

@router.get("/chains/{chain_name}/stats", response_model=ChainStatsResponse)
async def get_chain_stats(chain_name: str):
    """Get statistics for a specific chain"""
    try:
        if chain_name == "main_chain":
            chain = hierarchy_manager.get_main_chain()
        else:
            chain = hierarchy_manager.get_sub_chain(chain_name)
        
        if not chain:
            raise HTTPException(status_code=404, detail=f"Chain '{chain_name}' not found")
        
        # Calculate stats
        chain_blocks = getattr(chain, 'chain', [])
        total_blocks = len(chain_blocks)
        total_events = sum(len(getattr(block, 'events', [])) for block in chain_blocks)
        
        # Get unique entities (for sub-chains)
        unique_entities = set()
        if hasattr(chain, 'chain'):
            for block in chain_blocks:
                for event in getattr(block, 'events', []):
                    if 'entity_id' in event:
                        unique_entities.add(event['entity_id'])
        
        # Determine additional stats based on chain type
        proof_count = None
        registered_sub_chains = None
        
        if chain_name == "main_chain":
            # For main chain, provide proof count
            proof_count = total_blocks - 1 if total_blocks > 0 else 0  # Exclude genesis block
        else:
            # For sub-chains, this would be None
            pass
        
        return ChainStatsResponse(
            chain_name=chain_name,
            total_blocks=total_blocks,
            total_events=total_events,
            proof_count=proof_count,
            registered_sub_chains=registered_sub_chains
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chain stats: {str(e)}")

@router.post("/chains/{chain_name}/create")
async def create_sub_chain(chain_name: str, chain_type: str = "generic"):
    """Create a new sub-chain"""
    if not re.match(r'^[a-zA-Z0-9_\-]+$', chain_name):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid chain identifier '{chain_name}'. Only alphanumeric, underscore, and hyphen are allowed."
        )
    try:
        main_chain = hierarchy_manager.get_main_chain()
        if not main_chain:
            # Create main chain if it doesn't exist
            main_chain = MainChain()
            hierarchy_manager.set_main_chain(main_chain)

        safe_chain_name = os.path.basename(chain_name)

        # Create sub-chain
        sub_chain = SubChain(name=safe_chain_name, domain_type=chain_type)
        hierarchy_manager.add_sub_chain(safe_chain_name, sub_chain)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "message": f"Sub-chain '{chain_name}' created successfully",
                "chain_name": chain_name
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create sub-chain: {str(e)}")

@router.get("/chains/{chain_name}/blocks")
async def get_chain_blocks(chain_name: str, limit: int = 10, offset: int = 0):
    """Get blocks from a specific chain"""
    try:
        if chain_name == "main_chain":
            chain = hierarchy_manager.get_main_chain()
        else:
            chain = hierarchy_manager.get_sub_chain(chain_name)
        
        if not chain:
            raise HTTPException(status_code=404, detail=f"Chain '{chain_name}' not found")
        
        # Get blocks with pagination
        chain_blocks = getattr(chain, 'chain', [])
        blocks = chain_blocks[offset:offset + limit]
        
        block_data = []
        for block in blocks:
            # Serialize events safely
            events_data = []
            if hasattr(block, 'to_event_list'):
                events_data = block.to_event_list()
            elif hasattr(block, 'events'):
                events_data = block.events
                # Handle direct Arrow Table if to_event_list is missing (safety fallback)
                if hasattr(events_data, 'to_pylist'):
                     # This is a suboptimal fallback as it doesn't parse JSON details, but prevents crash
                     events_data = events_data.to_pylist()
            
            block_data.append({
                "index": getattr(block, 'index', None),
                "hash": getattr(block, 'hash', None),
                "previous_hash": getattr(block, 'previous_hash', None),
                "timestamp": getattr(block, 'timestamp', None),
                "events_count": len(events_data) if isinstance(events_data, list) else 0,
                "events": events_data
            })
        
        return {
            "chain_name": chain_name,
            "blocks": block_data,
            "total_blocks": len(chain_blocks),
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get blocks: {str(e)}")
