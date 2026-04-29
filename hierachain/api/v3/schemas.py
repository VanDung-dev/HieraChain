"""
Pydantic schemas for API v3 requests and responses (System Management)
"""

from typing import Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


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
                "challenge": "abcd1234"
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


class SecureEventRequest(BaseModel):
    """
    High-integrity event submission schema for API v3.
    Enforces strict synchronous validation of cryptographic proofs and payload depth.
    """
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "entity_id": "asset-001",
                "event_type": "transfer",
                "details": {"amount": 100, "currency": "HRC"},
                "sender": "0x1234567890abcdef...",
                "signature": "0xabcdef1234567890..."
            }
        }
    )

    entity_id: str = Field(..., min_length=1, max_length=128)
    event_type: str = Field(..., min_length=1, max_length=64)
    details: dict[str, Any] = Field(default_factory=dict)
    sender: str = Field(..., description="Hex-encoded sender identity")
    signature: str = Field(..., description="Hex-encoded digital signature")

    @field_validator('sender', 'signature')
    @classmethod
    def validate_hex_format(cls, v: str) -> str:
        """Enforce strict hex format for cryptographic fields."""
        if not v.startswith("0x"):
            raise ValueError("Cryptographic fields must start with '0x' prefix")
        try:
            bytes.fromhex(v[2:])
        except ValueError:
            raise ValueError("Field must be a valid hex string after '0x' prefix")
        return v

    @field_validator('details')
    @classmethod
    def validate_details_integrity(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Verify payload integrity, size, and depth to prevent recursion attacks."""
        import json
        if len(json.dumps(v)) > 1024 * 1024:
            raise ValueError("Event details exceed 1MB size limit")

        def check_depth(d, current_depth=0):
            if current_depth > 10:
                raise ValueError("Payload depth exceeds maximum limit (10)")
            if isinstance(d, dict):
                for value in d.values():
                    check_depth(value, current_depth + 1)
            elif isinstance(d, list):
                for item in d:
                    check_depth(item, current_depth + 1)

        check_depth(v)
        return v


class SecureEventResponse(BaseModel):
    """Response schema for high-integrity event submission"""
    status: str = Field(..., description="Operation status (always 'committed' for v3)")
    event_hash: str = Field(..., description="Cryptographic hash of the committed event")
    timestamp: float = Field(..., description="Server-side commit timestamp")
