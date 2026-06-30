"""
Pydantic schemas for API v1 requests and responses

This module defines the data models used for validating and serializing
API v1 requests and responses in the HieraChain system.
Each schema corresponds to specific API endpoints and ensures data integrity
and proper documentation.

IPFS Integration:
- Supports both on-chain data (dict) and off-chain data (IPFS CID)
- CID fields enable large payloads to be stored off-chain
- Backward compatible with existing on-chain data
"""

from typing import Any
from pydantic import (
    BaseModel, Field, ConfigDict, field_validator
)


class EventRequest(BaseModel):
    """
    Request schema for adding events.

    Supports both on-chain and off-chain data storage:
    - On-chain: Provide 'details' as a dict (traditional approach)
    - Off-chain: Provide 'details_cid' as IPFS CID and 'details_nonce' for decryption

    Note: If both 'details' and 'details_cid' are provided, 'details_cid' takes precedence.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "entity_id": "PRODUCT-2024-001",
                    "event_type": "production_start",
                    "details": {
                        "material_batch": "BATCH-001",
                        "machine_id": "MACHINE-07"
                    }
                },
                {
                    "entity_id": "PRODUCT-2024-002",
                    "event_type": "production_start",
                    "details_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
                    "details_nonce": "a1b2c3d4e5f6789012345678",
                    "details_metadata": {
                        "channel": "manufacturing",
                        "org": "acme_corp"
                    }
                }
            ]
        }
    )

    entity_id: str = Field(..., description="Unique identifier for the entity")
    event_type: str = Field(
        ..., description="Type of event (e.g., 'operation_start', 'status_change')"
    )

    # On-chain data (traditional)
    details: dict[str, Any] | None = Field(
        None,
        description="Event details stored on-chain (use for small payloads)"
    )

    # Off-chain data (IPFS)
    details_cid: str | None = Field(
        None,
        description="IPFS CID for off-chain event details (use for large payloads)"
    )
    details_nonce: str | None = Field(
        None,
        description="Encryption nonce (hex string) for decrypting IPFS data"
    )
    details_metadata: dict[str, Any] | None = Field(
        None,
        description="Metadata used as AAD during encryption (must match for decryption)"
    )

    # Cryptographic fields
    sender: str | None = Field(
        None,
        description="Public key or identity of the event sender"
    )
    signature: str | None = Field(
        None,
        description="Cryptographic signature of the event payload"
    )

    @field_validator('details')
    @classmethod
    def validate_details_integrity(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Prevent deeply nested structures and oversized payloads."""
        if v is None:
            return v
        
        # Check size (approximate via string conversion)
        import json
        if len(json.dumps(v)) > 1024 * 1024:
            raise ValueError("Event details exceed 1MB size limit")

        def get_depth(d, level=1):
            if level > 10:
                raise ValueError("Event details are too deeply nested (max depth 10)")
            if not isinstance(d, (dict, list)) or not d:
                return level
            if isinstance(d, list):
                return max((get_depth(item, level + 1) for item in d), default=level)
            return max((get_depth(val, level + 1) for val in d.values()), default=level)
            
        get_depth(v)
        return v

    @field_validator('sender', 'signature')
    @classmethod
    def validate_crypto_fields(cls, v: str | None, info: Any) -> str | None:
        """Strict validation of sender and signature fields."""
        if v is None:
            return v
            
        # 1. Hex format check
        hex_part = v.removeprefix("0x")
        try:
            bytes.fromhex(hex_part)
        except ValueError:
            raise ValueError(f"{info.field_name} must be a valid hex string")
            
        # 2. Minimum length check for security (Ed25519)
        if len(hex_part) < 64:
            raise ValueError(f"{info.field_name} too short for cryptographic verification")
            
        return v

    @field_validator('details_cid')
    @classmethod
    def validate_cid(cls, v: str | None) -> str | None:
        """Validate IPFS CID format."""
        if v is not None:
            # Basic CID validation (starts with Qm for CIDv0 or b for CIDv1)
            if not (v.startswith('Qm') or v.startswith('b')):
                raise ValueError(
                    'Invalid IPFS CID format. CID should start with "Qm" (v0) or "b" (v1)'
                )
            if len(v) < 46:  # Minimum CID length
                raise ValueError('Invalid IPFS CID: too short')
        return v

    @field_validator('details_nonce')
    @classmethod
    def validate_nonce_with_cid(cls, v: str | None, info) -> str | None:
        """Validate that nonce is provided when CID is present."""
        if info.data.get('details_cid') and not v:
            raise ValueError('details_nonce is required when details_cid is provided')
        if v is not None:
            # Validate hex format
            try:
                bytes.fromhex(v)
            except ValueError:
                raise ValueError('details_nonce must be a valid hex string')
            # Nonce should be 12 bytes = 24 hex chars for AES-GCM
            if len(v) != 24:
                raise ValueError('details_nonce must be 24 hex characters (12 bytes)')
        return v


class EventResponse(BaseModel):
    """Response schema for event operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Event added to chain 'production_chain'",
                "event_id": "production_chain_1_5"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    event_id: str | None = Field(None, description="Generated event ID")


class ChainInfoResponse(BaseModel):
    """Response schema for chain information"""
    model_config = ConfigDict(
        json_schema_extra={
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
    latest_block_hash: str | None = Field(None, description="Hash of the latest block")


class ProofSubmissionResponse(BaseModel):
    """Response schema for proof submission operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Proof from 'ProductionChain' added to Main Chain",
                "proof_id": "main_chain_5_2"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    proof_id: str | None = Field(None, description="Generated proof ID")


class EntityTraceResponse(BaseModel):
    """Response schema for entity tracing operations"""
    model_config = ConfigDict(
        json_schema_extra={
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
    chains: list[str] = Field(
        ..., description="List of chains where the entity has events"
    )
    events: list[dict[str, Any]] = Field(
        ..., description="List of events for the entity across chains"
    )


class ChainStatsResponse(BaseModel):
    """Response schema for chain statistics"""
    model_config = ConfigDict(
        json_schema_extra={
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
    proof_count: int | None = Field(
        None, description="Number of proofs (for Main Chain)"
    )
    registered_sub_chains: int | None = Field(
        None, description="Number of registered Sub-Chains (for Main Chain)"
    )
