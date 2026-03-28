"""
API v3 endpoints for System Management
"""

import time
import os
from fastapi import APIRouter, HTTPException, Depends
from hierachain.api.v3.schemas import (
    VerifyIdentityRequest, VerifyIdentityResponse, NodeStatusResponse
)
from hierachain.units.version import get_version
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.api.v1.endpoints import get_hierarchy_manager
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.config.settings import get_settings
from hierachain.security.key_provider import LocalKeyProvider, CryptoError
from hierachain.security.secure_logging import SecureLogger

logger = SecureLogger("hierachain.api.v3")


router = APIRouter(prefix="/api/v3", tags=["HieraChain-v3 (System & Admin)"])


def get_current_key_provider() -> LocalKeyProvider:
    """
    Dependency to get the active key provider with loaded identity.
    
    Raises:
        HTTPException(401): If identity file is missing or fails to load
    """
    settings = get_settings()
    identity_path = settings.VALIDATOR_IDENTITY_PATH
    
    if not os.path.exists(identity_path):
        logger.error(
            "Identity file not found, access denied",
            path=identity_path
        )
        raise HTTPException(
            status_code=401,
            detail="Node identity not configured. Please provide valid identity file."
        )
    
    try:
        logger.info("Loading node identity", path=identity_path)
        return LocalKeyProvider.from_file(identity_path)
    except CryptoError as e:
        logger.error("Failed to load node identity", error=str(e))
        raise HTTPException(
            status_code=401,
            detail=f"Failed to load node identity: {str(e)}"
        )


@router.post(
    "/verify-identity",
    response_model=VerifyIdentityResponse,
    dependencies=[Depends(require_chain_access)]
)
async def verify_identity(
    request: VerifyIdentityRequest,
    key_provider: LocalKeyProvider = Depends(get_current_key_provider)
):
    """
    Verify node identity by signing a challenge.
    Used by management tools to confirm this node is a legitimate member of the network.
    """
    try:
        signature = key_provider.sign(request.challenge.encode())
        return VerifyIdentityResponse(
            status="success",
            node_id="node_1",
            signature=signature,
            challenge=request.challenge
        )
    except Exception as e:
        logger.error("Identity verification failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Identity verification failed. An internal error has occurred."
        )


@router.get(
    "/status",
    response_model=NodeStatusResponse,
    dependencies=[Depends(require_chain_access)]
)
async def get_status(manager: HierarchyManager = Depends(get_hierarchy_manager)):
    """
    Get detailed node status report.
    """

    # Get active chains count from hierarchy manager
    chains_active = len(manager.get_all_sub_chains())

    # Calculate uptime
    uptime_seconds = time.time() - manager.system_started_at
    days, rem = divmod(int(uptime_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    if days > 0:
        uptime_str = f"{days}d {hours}h {minutes}m"
    else:
        uptime_str = f"{hours}h {minutes}m {seconds}s"

    # Check license status (mocked as true)
    license_active = True

    return NodeStatusResponse(
        status="active",
        version=get_version(),
        chains_active=chains_active,
        license_active=license_active,
        uptime=uptime_str
    )
