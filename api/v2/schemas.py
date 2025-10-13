"""
Pydantic schemas for API v2 requests and responses

This module defines the data models used for validating and serializing
API v2 requests and responses in the hierarchical blockchain system.
These schemas support the new enterprise security and data isolation features.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class ChannelCreateRequest(BaseModel):
    """Request schema for creating a new channel"""
    model_config = ConfigDict(
        json_schema_extra = {
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
    organizations: List[str] = Field(..., description="List of organization IDs participating in the channel")
    policy: Dict[str, Any] = Field(..., description="Channel access and endorsement policies")


class ChannelResponse(BaseModel):
    """Response schema for channel operations"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Channel 'manufacturing_channel' created successfully",
                "channel_id": "manufacturing_channel"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    channel_id: Optional[str] = Field(None, description="Channel identifier")


class PrivateCollectionCreateRequest(BaseModel):
    """Request schema for creating a private data collection"""
    model_config = ConfigDict(
        json_schema_extra = {
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
    members: List[str] = Field(..., description="List of organization IDs that are members of this collection")
    config: Dict[str, Any] = Field(..., description="Collection configuration parameters")


class PrivateDataRequest(BaseModel):
    """Request schema for adding private data"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
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
            }
        }
    )
    
    collection: str = Field(..., description="Name of the private collection")
    key: str = Field(..., description="Key for the private data")
    value: Dict[str, Any] = Field(..., description="Private data value")
    event_metadata: Dict[str, Any] = Field(..., description="Event metadata for endorsement verification")


class PrivateDataResponse(BaseModel):
    """Response schema for private data operations"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Private data added to collection 'sensitive_data_collection'",
                "key": "contract_terms_001"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    key: Optional[str] = Field(None, description="Key of the private data")


class ContractCreateRequest(BaseModel):
    """Request schema for creating a domain contract"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "contract_id": "quality_control_contract",
                "version": "1.0.0",
                "implementation": "def quality_control_logic(event, state, context): ...",
                "metadata": {
                    "domain": "manufacturing",
                    "owner": "org1",
                    "endorsement_policy": "MAJORITY"
                }
            }
        }
    )
    
    contract_id: str = Field(..., description="Unique identifier for the contract")
    version: str = Field(..., description="Semantic version of the contract")
    implementation: str = Field(..., description="Contract implementation code or reference")
    metadata: Dict[str, Any] = Field(..., description="Contract governance and configuration metadata")


class ContractExecuteRequest(BaseModel):
    """Request schema for executing a domain contract"""
    model_config = ConfigDict(
        json_schema_extra = {
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
    event: Dict[str, Any] = Field(..., description="Event to trigger contract execution")
    context: Dict[str, Any] = Field(..., description="Execution context")


class ContractResponse(BaseModel):
    """Response schema for contract operations"""
    model_config = ConfigDict(
        json_schema_extra = {
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
    contract_id: Optional[str] = Field(None, description="Contract identifier")
    result: Optional[Dict[str, Any]] = Field(None, description="Result of contract execution")


class OrganizationRequest(BaseModel):
    """Request schema for organization operations"""
    model_config = ConfigDict(
        json_schema_extra = {
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
    ca_config: Dict[str, Any] = Field(..., description="Certificate authority configuration")


class OrganizationResponse(BaseModel):
    """Response schema for organization operations"""
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Organization 'manufacturer_org' registered successfully",
                "org_id": "manufacturer_org"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    org_id: Optional[str] = Field(None, description="Organization identifier")