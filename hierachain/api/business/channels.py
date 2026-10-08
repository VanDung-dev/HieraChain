"""API business — channel management endpoints.

Create channels and manage private data collections within channels.
"""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from hierachain.api.business.schemas import (
    ChannelCreateRequest,
    ChannelResponse,
    PrivateCollectionCreateRequest,
)
from hierachain.api.business.state import _private_collections
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.sanitization import sanitize_dict, sanitize_string
from hierachain.security.secure_logging import SecureLogger
from hierachain.security.verify.api_key_verifier import (
    ResourcePermissionChecker,
    require_chain_access,
)

router = APIRouter(tags=["HieraChain-business"])
api_logger = SecureLogger("hierachain.api.business")


@router.post(
    "/channels",
    response_model=ChannelResponse,
)
async def create_channel(
    channel_request: ChannelCreateRequest,
    auth_context: dict[str, Any] = Depends(require_chain_access),
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> ChannelResponse:
    if not ResourcePermissionChecker.has_permission(auth_context, "channels:manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Channel provisioning requires 'channels:manage' permission.",
        )

    try:
        channel_id = sanitize_string(channel_request.channel_id)
        org_ids = [sanitize_string(org_id) for org_id in channel_request.organizations]
        policy = sanitize_dict(channel_request.policy)
        if not channel_id or not org_ids or any(not org_id for org_id in org_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Channel ID and at least one valid organization ID are required.",
            )
        if manager.get_channel(channel_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Channel '{channel_id}' already exists.",
            )
        for org_id in org_ids:
            if manager.get_organization(org_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Organization '{org_id}' not found.",
                )

        manager.create_channel(channel_id, org_ids, policy)
        api_logger.audit(
            action="create",
            resource="channel",
            success=True,
            channel_id=channel_id,
            org_count=len(org_ids)
        )

        return ChannelResponse(
            success=True,
            message=f"Channel '{channel_id}' created successfully",
            channel_id=channel_id
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel '{channel_request.channel_id}' could not be created.",
        ) from e
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
async def get_channel(
    channel_id: str,
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> ChannelResponse:
    if manager.get_channel(channel_id) is None:
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
    channel_id: str,
    collection_request: PrivateCollectionCreateRequest,
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> ChannelResponse:
    channel = manager.get_channel(channel_id)
    if channel is None:
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
        if not collection_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Collection name cannot be empty.",
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
    except HTTPException:
        raise
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
