"""
API endpoints for Hierarchical Blockchain Framework

This module provides RESTful API endpoints for interacting with the hierarchical blockchain system.
The system follows a two-level architecture where sub-chains handle business events and the main chain
stores cryptographic proofs from sub-chains.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import time

from .schemas import (
    EventRequest, EventResponse, ChainInfoResponse, 
    ProofSubmissionRequest, ProofSubmissionResponse,
    EntityTraceResponse, ChainStatsResponse
)
from hierarchical.main_chain import MainChain
from hierarchical.sub_chain import SubChain
from hierarchical.hierarchy_manager import HierarchyManager
from domains.generic.utils.entity_tracer import EntityTracer

router = APIRouter(prefix="/api/v1", tags=["hierarchical-blockchain"])

# Global instances (in production, use dependency injection)
hierarchy_manager = HierarchyManager()
entity_tracer = EntityTracer(hierarchy_manager)

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@router.get("/chains", response_model=List[ChainInfoResponse])
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
                block_count=len(main_chain.chain),
                latest_block_hash=main_chain.get_latest_block().hash if main_chain.chain else None,
                parent_chain=None
            ))
        
        # Add sub-chains info
        for sub_chain_name, sub_chain in hierarchy_manager.get_all_sub_chains().items():
            chains.append(ChainInfoResponse(
                name=sub_chain_name,
                type="sub",
                block_count=len(sub_chain.chain),
                latest_block_hash=sub_chain.get_latest_block().hash if sub_chain.chain else None,
                parent_chain="main_chain"
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
async def submit_proof(chain_name: str, proof_request: ProofSubmissionRequest):
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
        if proof_request.metadata:
            metadata_filter = lambda chain: proof_request.metadata
        
        sub_chain.submit_proof_to_main(main_chain, metadata_filter)
        
        return ProofSubmissionResponse(
            success=True,
            message=f"Proof submitted from '{chain_name}' to main chain",
            proof_hash=sub_chain.get_latest_block().hash if sub_chain.chain else None
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
            
            events = entity_tracer.trace_entity_in_chain(entity_id, sub_chain)
        else:
            # Trace across all chains
            events = entity_tracer.trace_entity_across_chains(entity_id, hierarchy_manager.get_all_sub_chains())
        
        return EntityTraceResponse(
            entity_id=entity_id,
            events=events,
            total_events=len(events)
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
        total_blocks = len(chain.chain)
        total_events = sum(len(block.events) for block in chain.chain)
        
        # Get unique entities (for sub-chains)
        unique_entities = set()
        if hasattr(chain, 'chain'):
            for block in chain.chain:
                for event in block.events:
                    if 'entity_id' in event:
                        unique_entities.add(event['entity_id'])
        
        return ChainStatsResponse(
            chain_name=chain_name,
            total_blocks=total_blocks,
            total_events=total_events,
            unique_entities=len(unique_entities),
            latest_block_hash=chain.get_latest_block().hash if chain.chain else None,
            created_at=getattr(chain, 'created_at', time.time())
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chain stats: {str(e)}")

@router.post("/chains/{chain_name}/create")
async def create_sub_chain(chain_name: str, chain_type: str = "generic"):
    """Create a new sub-chain"""
    try:
        main_chain = hierarchy_manager.get_main_chain()
        if not main_chain:
            # Create main chain if it doesn't exist
            main_chain = MainChain()
            hierarchy_manager.set_main_chain(main_chain)
        
        # Create sub-chain
        sub_chain = SubChain(name=chain_name, parent_chain=main_chain)
        hierarchy_manager.add_sub_chain(chain_name, sub_chain)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "message": f"Sub-chain '{chain_name}' created successfully",
                "chain_type": chain_type
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
        blocks = chain.chain[offset:offset + limit]
        
        block_data = []
        for block in blocks:
            block_data.append({
                "index": block.index,
                "hash": block.hash,
                "previous_hash": block.previous_hash,
                "timestamp": block.timestamp,
                "events_count": len(block.events),
                "events": block.events
            })
        
        return {
            "chain_name": chain_name,
            "blocks": block_data,
            "total_blocks": len(chain.chain),
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get blocks: {str(e)}")