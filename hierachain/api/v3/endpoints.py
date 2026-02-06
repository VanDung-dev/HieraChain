"""
API v3 endpoints for System Management
"""

import time
import logging
import os
from fastapi import APIRouter, HTTPException, Depends
from hierachain.api.v3.schemas import (
    VerifyIdentityRequest, VerifyIdentityResponse, NodeStatusResponse
)
from hierachain.units.version import get_version
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.api.v1.endpoints import get_hierarchy_manager
from hierachain.config.settings import get_settings
from hierachain.security.key_provider import LocalKeyProvider, CryptoError

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v3", tags=["System & Admin"])


def get_current_key_provider() -> LocalKeyProvider:
    """Dependency to get the active key provider with loaded identity."""
    settings = get_settings()
    identity_path = settings.VALIDATOR_IDENTITY_PATH
    
    try:
        if os.path.exists(identity_path):
            logger.info(f"Loading node identity from {identity_path}")
            return LocalKeyProvider.from_file(identity_path)
        else:
            logger.warning(f"Identity file {identity_path} not found. Using ephemeral key.")
            return LocalKeyProvider.generate()
    except CryptoError as e:
        logger.error(f"Failed to load node identity: {e}")
        return LocalKeyProvider.generate()


@router.post("/verify-identity", response_model=VerifyIdentityResponse)
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
            node_id="node_1",  # In a multi-node setup, this would be the actual node name
            signature=signature,
            challenge=request.challenge
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Identity verification failed: {str(e)}")


@router.get("/status", response_model=NodeStatusResponse)
async def get_status(manager: HierarchyManager = Depends(get_hierarchy_manager)):
    """
    Get detailed node status report.
    """
    settings = get_settings()

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
