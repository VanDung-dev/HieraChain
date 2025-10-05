"""
Pydantic schemas for API v1 requests and responses

This module defines the data models used for validating and serializing
API v1 requests and responses in the hierarchical blockchain system.
Each schema corresponds to specific API endpoints and ensures data integrity
and proper documentation.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class EventRequest(BaseModel):
    """Request schema for adding events"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "entity_id": "PRODUCT-2024-001",
                "event_type": "production_start",
                "details": {
                    "material_batch": "BATCH-001",
                    "machine_id": "MACHINE-07"
                }
            }
        }
    )
    
    entity_id: str = Field(..., description="Unique identifier for the entity")
    event_type: str = Field(..., description="Type of event (e.g., 'operation_start', 'status_change')")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional event details")


class EventResponse(BaseModel):
    """Response schema for event operations"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Event added to chain 'production_chain'",
                "event_id": "production_chain_1_5"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    event_id: Optional[str] = Field(None, description="Generated event ID")


class ChainInfoResponse(BaseModel):
    """Response schema for chain information"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "name": "ProductionChain",
                "type": "sub",
                "block_count": 5,
                "latest_block_hash": "a1b2c3d4e5f6..."
            }
        }
    )
    
    name: str = Field(..., description="Chain name")
    type: str = Field(..., description="Chain type (main or sub)")
    block_count: int = Field(..., description="Number of blocks in the chain")
    latest_block_hash: Optional[str] = Field(None, description="Hash of the latest block")


class ProofSubmissionRequest(BaseModel):
    """Request schema for submitting proofs to Main Chain"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "sub_chain_name": "ProductionChain",
                "proof_hash": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "metadata": {
                    "domain_type": "manufacturing",
                    "operations_count": 10
                }
            }
        }
    )
    
    sub_chain_name: str = Field(..., description="Name of the Sub-Chain submitting the proof")
    proof_hash: str = Field(..., description="Cryptographic hash of the Sub-Chain's latest block")
    metadata: Dict[str, Any] = Field(..., description="Summary metadata about the Sub-Chain's operations")


class ProofSubmissionResponse(BaseModel):
    """Response schema for proof submission operations"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Proof from 'ProductionChain' added to Main Chain",
                "proof_id": "main_chain_5_2"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    proof_id: Optional[str] = Field(None, description="Generated proof ID")


class EntityTraceResponse(BaseModel):
    """Response schema for entity tracing operations"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "entity_id": "PRODUCT-2024-001",
                "chains": ["ProductionChain", "QualityChain", "ShippingChain"],
                "events": [
                    {
                        "chain": "ProductionChain",
                        "event_type": "production_start",
                        "timestamp": 1717987200.0
                    },
                    {
                        "chain": "QualityChain", 
                        "event_type": "quality_check",
                        "timestamp": 1717987500.0
                    }
                ]
            }
        }
    )
    
    entity_id: str = Field(..., description="Entity identifier being traced")
    chains: List[str] = Field(..., description="List of chains where the entity has events")
    events: List[Dict[str, Any]] = Field(..., description="List of events for the entity across chains")


class ChainStatsResponse(BaseModel):
    """Response schema for chain statistics"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "chain_name": "MainChain",
                "total_blocks": 100,
                "total_events": 1500,
                "proof_count": 50,
                "registered_sub_chains": 5
            }
        }
    )
    
    chain_name: str = Field(..., description="Name of the chain")
    total_blocks: int = Field(..., description="Total number of blocks in the chain")
    total_events: int = Field(..., description="Total number of events in the chain")
    proof_count: Optional[int] = Field(None, description="Number of proofs (for Main Chain)")
    registered_sub_chains: Optional[int] = Field(None, description="Number of registered Sub-Chains (for Main Chain)")


class CreateChainRequest(BaseModel):
    """Request schema for creating a new chain"""
    chain_type: str = Field(..., description="Type of chain to create")
    participants: Optional[List[str]] = Field(None, description="List of participants")
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "chain_type": "supply_chain",
                "participants": ["manufacturer", "supplier", "distributor"]
            }
        }
    )


class CreateChainResponse(BaseModel):
    """Response schema for chain creation"""
    success: bool = Field(..., description="Whether the chain creation was successful")
    message: str = Field(..., description="Response message")
    chain_name: str = Field(..., description="Name of the created chain")
    chain_type: str = Field(..., description="Type of the created chain")
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Sub-chain 'production_chain' created successfully",
                "chain_name": "production_chain",
                "chain_type": "generic"
            }
        }
    )