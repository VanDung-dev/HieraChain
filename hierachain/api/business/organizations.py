"""API v2 — organisation management endpoints.

Register and query organisations with their CA configuration.
"""

import time
from fastapi import APIRouter, HTTPException, status, Depends

from hierachain.api.business.schemas import OrganizationRequest, OrganizationResponse
from hierachain.security.sanitization import sanitize_string, sanitize_dict
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.security.secure_logging import SecureLogger

from hierachain.api.business.state import _organizations

router = APIRouter(tags=["HieraChain-v2"])
api_logger = SecureLogger("hierachain.api.business")


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    dependencies=[Depends(require_chain_access)]
)
async def register_organization(org_request: OrganizationRequest):
    try:
        org_id = sanitize_string(org_request.org_id)
        safe_ca_config = (
            sanitize_dict(org_request.ca_config) if org_request.ca_config else {}
        )

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


@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationResponse,
    dependencies=[Depends(require_chain_access)]
)
async def get_organization(org_id: str):
    if org_id not in _organizations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found"
        )

    return OrganizationResponse(
        success=True,
        message=f"Organization '{org_id}' found",
        org_id=org_id
    )
