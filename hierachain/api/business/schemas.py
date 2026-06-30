"""
Pydantic schemas for API v2 requests and responses

This module defines the data models used for validating and serializing
API v2 requests and responses in the HieraChain system.
These schemas support the new enterprise security and data isolation features.

IPFS Integration:
- Supports both on-chain data (dict/str) and off-chain data (IPFS CID)
- CID fields enable large payloads (contracts, private data) to be stored off-chain
- Backward compatible with existing on-chain data
"""

from typing import Any
from pydantic import (
    BaseModel, Field, ConfigDict, field_validator
)


class ChannelCreateRequest(BaseModel):
    """Request schema for creating a new channel"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channel_id": "manufacturing_channel",
                "organizations": ["org1", "org2", "org3"],
                "policy": {
                    "read": "ADMIN || MEMBER",
                    "write": "ADMIN",
                    "endorsement": "MAJORITY"
                }
            }
        }
    )
    
    channel_id: str = Field(..., description="Unique identifier for the channel")
    organizations: list[str] = Field(
        ..., description="List of organization IDs participating in the channel"
    )
    policy: dict[str, Any] = Field(
        ..., description="Channel access and endorsement policies"
    )


class ChannelResponse(BaseModel):
    """Response schema for channel operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Channel 'manufacturing_channel' created successfully",
                "channel_id": "manufacturing_channel"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    channel_id: str | None = Field(None, description="Channel identifier")


class PrivateCollectionCreateRequest(BaseModel):
    """Request schema for creating a private data collection"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "sensitive_data_collection",
                "members": ["org1", "org2"],
                "config": {
                    "block_to_purge": 1000,
                    "endorsement_policy": "MAJORITY"
                }
            }
        }
    )
    
    name: str = Field(..., description="Name of the private collection")
    members: list[str] = Field(
        ..., description="List of organization IDs that are members of this collection"
    )
    config: dict[str, Any] = Field(
        ..., description="Collection configuration parameters"
    )


class PrivateDataRequest(BaseModel):
    """
    Request schema for adding private data.

    Supports both on-chain and off-chain storage:
    - On-chain: Provide 'value' as a dict (traditional approach)
    - Off-chain: Provide 'value_cid' as IPFS CID and 'value_nonce' for decryption

    Note: Off-chain storage is recommended for sensitive/large private data.
    If both 'value' and 'value_cid' are provided, 'value_cid' takes precedence.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "collection": "sensitive_data_collection",
                    "key": "contract_terms_001",
                    "value": {
                        "price": 10000,
                        "discount": 0.1,
                        "payment_terms": "NET30"
                    },
                    "event_metadata": {
                        "entity_id": "CONTRACT-2024-001",
                        "event": "contract_negotiation",
                        "timestamp": 1717987200.0
                    }
                },
                {
                    "collection": "sensitive_data_collection",
                    "key": "contract_terms_002",
                    "value_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
                    "value_nonce": "a1b2c3d4e5f6789012345678",
                    "value_metadata": {
                        "collection": "sensitive_data_collection",
                        "channel": "finance"
                    },
                    "event_metadata": {
                        "entity_id": "CONTRACT-2024-002",
                        "event": "contract_negotiation",
                        "timestamp": 1717987200.0
                    }
                }
            ]
        }
    )

    collection: str = Field(..., description="Name of the private collection")
    key: str = Field(..., description="Key for the private data")

    # On-chain data (traditional)
    value: dict[str, Any] | None = Field(
        None,
        description="Private data value stored on-chain (use for small payloads)"
    )

    # Off-chain data (IPFS) - recommended for private data
    value_cid: str | None = Field(
        None,
        description="IPFS CID for off-chain private data (recommended for sensitive/large data)"
    )
    value_nonce: str | None = Field(
        None,
        description="Encryption nonce (hex string) for decrypting IPFS data"
    )
    value_metadata: dict[str, Any] | None = Field(
        None,
        description="Metadata used as AAD during encryption (must match for decryption)"
    )

    event_metadata: dict[str, Any] = Field(
        ..., description="Event metadata for endorsement verification"
    )

    @field_validator('value_cid')
    @classmethod
    def validate_cid(cls, v: str | None) -> str | None:
        """Validate IPFS CID format."""
        if v is not None:
            if not (v.startswith('Qm') or v.startswith('b')):
                raise ValueError(
                    'Invalid IPFS CID format. CID should start with "Qm" (v0) or "b" (v1)'
                )
            if len(v) < 46:
                raise ValueError('Invalid IPFS CID: too short')
        return v

    @field_validator('value_nonce')
    @classmethod
    def validate_nonce_with_cid(cls, v: str | None, info) -> str | None:
        """Validate that nonce is provided when CID is present."""
        if info.data.get('value_cid') and not v:
            raise ValueError('value_nonce is required when value_cid is provided')
        if v is not None:
            try:
                bytes.fromhex(v)
            except ValueError:
                raise ValueError('value_nonce must be a valid hex string')
            if len(v) != 24:
                raise ValueError('value_nonce must be 24 hex characters (12 bytes)')
        return v


class PrivateDataResponse(BaseModel):
    """Response schema for private data operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": (
                    "Private data added to collection 'sensitive_data_collection'"
                ),
                "key": "contract_terms_001"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    key: str | None = Field(None, description="Key of the private data")


class ContractCreateRequest(BaseModel):
    """
    Request schema for creating a domain contract.

    Supports both on-chain and off-chain contract code storage:
    - On-chain: Provide 'implementation' as a string (traditional approach)
    - Off-chain: Provide 'implementation_cid' as IPFS CID and 'implementation_nonce' for decryption

    Note: Off-chain storage is recommended for large contract implementations.
    If both 'implementation' and 'implementation_cid' are provided, 'implementation_cid' takes precedence.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "contract_id": "quality_control_contract",
                    "version": "1.0.0",
                    "implementation": (
                        "def quality_control_logic(event, state, context): ..."
                    ),
                    "metadata": {
                        "domain": "manufacturing",
                        "owner": "org1",
                        "endorsement_policy": "MAJORITY"
                    }
                },
                {
                    "contract_id": "supply_chain_contract",
                    "version": "2.0.0",
                    "implementation_cid": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
                    "implementation_nonce": "a1b2c3d4e5f6789012345678",
                    "implementation_metadata": {
                        "contract_id": "supply_chain_contract",
                        "channel": "supply_chain"
                    },
                    "metadata": {
                        "domain": "supply_chain",
                        "owner": "org2",
                        "endorsement_policy": "MAJORITY"
                    }
                }
            ]
        }
    )

    contract_id: str = Field(..., description="Unique identifier for the contract")
    version: str = Field(..., description="Semantic version of the contract")

    # On-chain implementation (traditional)
    implementation: str | None = Field(
        None,
        description="Contract implementation code stored on-chain (use for small contracts)"
    )

    # Off-chain implementation (IPFS) - recommended for large contracts
    implementation_cid: str | None = Field(
        None,
        description="IPFS CID for off-chain contract implementation (recommended for large code)"
    )
    implementation_nonce: str | None = Field(
        None,
        description="Encryption nonce (hex string) for decrypting IPFS data"
    )
    implementation_metadata: dict[str, Any] | None = Field(
        None,
        description="Metadata used as AAD during encryption (must match for decryption)"
    )

    metadata: dict[str, Any] = Field(
        ..., description="Contract governance and configuration metadata"
    )

    @field_validator('implementation_cid')
    @classmethod
    def validate_cid(cls, v: str | None) -> str | None:
        """Validate IPFS CID format."""
        if v is not None:
            if not (v.startswith('Qm') or v.startswith('b')):
                raise ValueError(
                    'Invalid IPFS CID format. CID should start with "Qm" (v0) or "b" (v1)'
                )
            if len(v) < 46:
                raise ValueError('Invalid IPFS CID: too short')
        return v

    @field_validator('implementation_nonce')
    @classmethod
    def validate_nonce_with_cid(cls, v: str | None, info) -> str | None:
        """Validate that nonce is provided when CID is present."""
        if info.data.get('implementation_cid') and not v:
            raise ValueError('implementation_nonce is required when implementation_cid is provided')
        if v is not None:
            try:
                bytes.fromhex(v)
            except ValueError:
                raise ValueError('implementation_nonce must be a valid hex string')
            if len(v) != 24:
                raise ValueError('implementation_nonce must be 24 hex characters (12 bytes)')
        return v

    @field_validator('implementation')
    @classmethod
    def validate_at_least_one_implementation(cls, v: str | None, info) -> str | None:
        """Ensure at least one of implementation or implementation_cid is provided."""
        if not v and not info.data.get('implementation_cid'):
            raise ValueError(
                'Either implementation or implementation_cid must be provided'
            )
        return v


class ContractExecuteRequest(BaseModel):
    """Request schema for executing a domain contract"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_id": "quality_control_contract",
                "event": {
                    "entity_id": "PRODUCT-2024-001",
                    "event": "quality_check",
                    "timestamp": 1717987200.0,
                    "details": {
                        "result": "pass",
                        "inspector_id": "INSPECTOR-03"
                    }
                },
                "context": {
                    "chain": "quality_chain"
                }
            }
        }
    )
    
    contract_id: str = Field(..., description="Identifier of the contract to execute")
    event: dict[str, Any] = Field(
        ..., description="Event to trigger contract execution"
    )
    context: dict[str, Any] = Field(..., description="Execution context")


class ContractResponse(BaseModel):
    """Response schema for contract operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Contract 'quality_control_contract' executed successfully",
                "contract_id": "quality_control_contract",
                "result": {
                    "status": "approved",
                    "next_step": "shipping"
                }
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    contract_id: str | None = Field(None, description="Contract identifier")
    result: dict[str, Any] | None = Field(
        None, description="Result of contract execution"
    )


class OrganizationRequest(BaseModel):
    """Request schema for organization operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "org_id": "manufacturer_org",
                "ca_config": {
                    "root_cert": "-----BEGIN CERTIFICATE-----...",
                    "intermediate_certs": ["-----BEGIN CERTIFICATE-----..."],
                    "policy": {
                        "certificate_lifetimes": {
                            "root": 3650,
                            "intermediate": 1825,
                            "entity": 365
                        }
                    }
                }
            }
        }
    )
    
    org_id: str = Field(..., description="Unique organization identifier")
    ca_config: dict[str, Any] = Field(
        ..., description="Certificate authority configuration"
    )


class OrganizationResponse(BaseModel):
    """Response schema for organization operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Organization 'manufacturer_org' registered successfully",
                "org_id": "manufacturer_org"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    org_id: str | None = Field(None, description="Organization identifier")
