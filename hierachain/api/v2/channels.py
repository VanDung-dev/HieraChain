"""API v2 — channel management endpoints.

Create channels and manage private data collections within channels.
"""

import time
from fastapi import APIRouter, HTTPException, status, Depends

from hierachain.api.v2.schemas import (
    ChannelCreateRequest, ChannelResponse,
    PrivateCollectionCreateRequest,
)
from hierachain.security.sanitization import sanitize_string, sanitize_dict
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.security.secure_logging import SecureLogger

from hierachain.api.v2.state import _channels, _private_collections

router = APIRouter(tags=["HieraChain-v2"])
api_logger = SecureLogger("hierachain.api.v2")


@router.post(
    "/channels",
    response_model=ChannelResponse,
    dependencies=[Depends(require_chain_access)]
)
async def create_channel(channel_request: ChannelCreateRequest):
    try:
        channel_id = channel_request.channel_id
        _channels[channel_id] = {
            "id": channel_id,
            "organizations": channel_request.organizations,
            "policy": channel_request.policy,
            "created_at": time.time()
        }

        api_logger.audit(
            action="create",
            resource="channel",
            success=True,
            channel_id=channel_id,
            org_count=len(channel_request.organizations)
        )

        return ChannelResponse(
            success=True,
            message=f"Channel '{channel_id}' created successfully",
            channel_id=channel_id
        )
    except Exception as e:
        api_logger.error(
            "Failed to create channel",
            error=str(e),
            channel_id=channel_request.channel_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create channel. An internal error has occurred."
        )


@router.get(
    "/channels/{channel_id}",
    response_model=ChannelResponse,
    dependencies=[Depends(require_chain_access)]
)
async def get_channel(channel_id: str):
    if channel_id not in _channels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel '{channel_id}' not found"
        )

    return ChannelResponse(
        success=True,
        message=f"Channel '{channel_id}' found",
        channel_id=channel_id
    )


@router.post(
    "/channels/{channel_id}/private-collections",
    response_model=ChannelResponse,
    dependencies=[Depends(require_chain_access)]
)
async def create_private_collection(
    channel_id: str, collection_request: PrivateCollectionCreateRequest
):
    if channel_id not in _channels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel '{channel_id}' not found"
        )

    try:
        collection_name = sanitize_string(collection_request.name)
        safe_members = (
            [sanitize_string(m) for m in collection_request.members]
            if collection_request.members else []
        )
        safe_config = (
            sanitize_dict(collection_request.config)
            if collection_request.config else {}
        )

        _private_collections[collection_name] = {
            "name": collection_name,
            "channel_id": channel_id,
            "members": safe_members,
            "config": safe_config,
            "created_at": time.time()
        }

        api_logger.audit(
            action="create",
            resource="private_collection",
            success=True,
            collection_name=collection_name,
            channel_id=channel_id,
        )

        return ChannelResponse(
            success=True,
            message=(
                f"Private collection '{collection_name}'"
                f"created in channel '{channel_id}'"
            ),
            channel_id=channel_id
        )
    except Exception as e:
        api_logger.error(
            "Failed to create private collection",
            error=str(e),
            channel_id=channel_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create private collection. An internal error has occurred."
        )
