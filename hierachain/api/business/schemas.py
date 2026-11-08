"""
Pydantic schemas for API business requests and responses

This module defines the data models used for validating and serializing
API business requests and responses in the HieraChain system.
These schemas support the new enterprise security and data isolation features.

IPFS Integration:
- Supports both on-chain data (dict/str) and off-chain data (IPFS CID)
- CID fields enable large payloads (contracts, private data) to be stored off-chain
- Backward compatible with existing on-chain data
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class OrganizationMemberRequest(BaseModel):
    """Request schema for an organization administrator to register a member."""

    member_id: str = Field(
        ..., min_length=1, description="User ID from the member's API key"
    )
    role: Literal["admin", "member"] = Field(
        "member", description="Role granted by an existing organization administrator"
    )


class OrganizationMemberResponse(BaseModel):
    """Response schema for organization member registration."""

    success: bool
    message: str
    org_id: str
    member_id: str
    role: str
