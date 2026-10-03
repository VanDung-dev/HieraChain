"""API business — organisation management endpoints.

Register and query organisations with their CA configuration.
"""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from hierachain.api.business.schemas import (
    OrganizationMemberRequest,
    OrganizationMemberResponse,
    OrganizationRequest,
    OrganizationResponse,
)
from hierachain.api.business.state import _organizations
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.hierarchical.hierarchy_manager.organization import (
    _is_organization_admin,
)
from hierachain.hierarchical.types import OrganizationError
from hierachain.security.sanitization import sanitize_dict, sanitize_string
from hierachain.security.secure_logging import SecureLogger
from hierachain.security.verify.api_key_verifier import (
    ResourcePermissionChecker,
    require_chain_access,
)

router = APIRouter(tags=["HieraChain-business"])
api_logger = SecureLogger("hierachain.api.business")


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
)
async def register_organization(
    org_request: OrganizationRequest,
    auth_context: dict[str, Any] = Depends(require_chain_access),
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> OrganizationResponse:
    if not ResourcePermissionChecker.has_permission(
        auth_context, "organizations:manage"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization provisioning requires 'organizations:manage' permission.",
        )

    user_id = auth_context.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An authenticated user is required to provision an organization.",
        )

    try:
        org_id = sanitize_string(org_request.org_id)
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Organization ID cannot be empty.",
            )
        safe_ca_config = (
            sanitize_dict(org_request.ca_config) if org_request.ca_config else {}
        )

        if manager.get_organization(org_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization '{org_id}' already exists.",
            )

        manager.create_organization(org_id, org_id, admin_users=[user_id])
        _organizations[org_id] = {
            "id": org_id,
            "ca_config": safe_ca_config,
            "registered_at": time.time()
        }

        api_logger.audit(
            action="register",
            resource="organization",
            success=True,
            org_id=org_id,
        )

        return OrganizationResponse(
            success=True,
            message=f"Organization '{org_id}' registered successfully",
            org_id=org_id
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization '{org_request.org_id}' could not be created.",
        ) from e
    except Exception as e:
        api_logger.error(
            "Failed to register organization",
            error=str(e),
            org_id=org_request.org_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register organization. An internal error has occurred."
        )


@router.post(
    "/organizations/{org_id}/members",
    response_model=OrganizationMemberResponse,
)
async def register_organization_member(
    org_id: str,
    member_request: OrganizationMemberRequest,
    auth_context: dict[str, Any] = Depends(require_chain_access),
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> OrganizationMemberResponse:
    user_id = auth_context.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An authenticated organization administrator is required.",
        )

    organization = manager.get_organization(org_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found.",
        )

    if not _is_organization_admin(organization, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a registered organization administrator can add members.",
        )

    member_id = sanitize_string(member_request.member_id)
    if not member_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Member ID cannot be empty.",
        )
    if member_id in organization.members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Member '{member_id}' is already registered.",
        )

    role = member_request.role
    identity = {"user_id": member_id, "org_id": org_id, "role": role}
    try:
        manager.register_organization_member(org_id, member_id, identity, role, actor_user_id=user_id)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a registered organization administrator can add members.",
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Member identity could not be registered.",
        ) from e
    except OrganizationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Member identity could not be registered.",
        ) from e
    except RuntimeError as e:
        api_logger.error(
            "Failed to persist organization member",
            org_id=org_id,
            member_id=member_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register organization member. An internal error has occurred.",
        ) from e

    api_logger.audit(
        action="register_member",
        resource="organization_member",
        success=True,
        org_id=org_id,
        member_id=member_id,
        role=role,
    )
    return OrganizationMemberResponse(
        success=True,
        message=f"Member '{member_id}' registered in organization '{org_id}'.",
        org_id=org_id,
        member_id=member_id,
        role=role,
    )


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    dependencies=[Depends(require_chain_access)]
)
async def get_organization(
    org_id: str,
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> OrganizationResponse:
    if manager.get_organization(org_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found"
        )

    return OrganizationResponse(
        success=True,
        message=f"Organization '{org_id}' found",
        org_id=org_id
    )
