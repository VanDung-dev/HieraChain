"""
Pydantic schemas for API v3 requests and responses (System Management)
"""

from pydantic import BaseModel, Field, ConfigDict


class VerifyIdentityRequest(BaseModel):
    """Request schema for node identity verification"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "challenge": "abcd1234"
            }
        }
    )

    challenge: str = Field(..., description="Challenge string to sign (hex encoded)")


class VerifyIdentityResponse(BaseModel):
    """Response schema for node identity verification"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "node_id": "node_1",
                "signature": "abcd1234_signed_by_node",
                "challenge_received": "abcd1234"
            }
        }
    )

    status: str = Field(..., description="Operation status")
    node_id: str = Field(..., description="Identifier of the node")
    signature: str = Field(..., description="Digital signature of the challenge")
    challenge: str = Field(..., description="The original challenge received")


class NodeStatusResponse(BaseModel):
    """Response schema for node status reports"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "active",
                "version": "0.1.0",
                "chains_active": 5,
                "license_active": True,
                "uptime": "1d 2h 30m"
            }
        }
    )

    status: str = Field(..., description="Current status of the node")
    version: str = Field(..., description="Ledgerrsion")
    chains_active: int = Field(..., description="Number of currently active chains")
    license_active: bool = Field(..., description="Whether a valid license is active")
    uptime: str = Field(..., description="Node uptime duration")


class InjectLicenseRequest(BaseModel):
    """Request schema for injecting a license key"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "license_key": "abcdef123456..."
            }
        }
    )

    license_key: str = Field(..., description="License key string")


class InjectLicenseResponse(BaseModel):
    """Response schema for license injection"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "message": "License key injected successfully"
            }
        }
    )

    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Status message")
