"""
API admin endpoints for System Management
"""

import time
import os
from fastapi import (
    APIRouter, HTTPException, status, Depends
)
from hierachain.api.admin.schemas import (
    VerifyIdentityRequest, VerifyIdentityResponse, NodeStatusResponse,
    SecureEventRequest, SecureEventResponse
)
from hierachain.config.version import get_version
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.config.settings import get_settings
from hierachain.security.key_provider import LocalKeyProvider, CryptoError
from hierachain.security.secure_logging import SecureLogger
from hierachain.security.verify.signature_verifier import SignatureVerifier

logger = SecureLogger("hierachain.api.admin")
router = APIRouter(prefix="/api/admin", tags=["HieraChain-admin (System & Admin)"])

verifier = SignatureVerifier()


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
        settings = get_settings()
        return VerifyIdentityResponse(
            status="success",
            node_id=settings.NODE_ID,
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


@router.post(
    "/chains/{chain_name}/secure-events",
    response_model=SecureEventResponse,
    dependencies=[Depends(require_chain_access)]
)
async def add_secure_event(
    chain_name: str,
    request: SecureEventRequest,
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    """
    High-integrity event submission.
    Mandates synchronous validation of signatures and data integrity.
    """
    try:
        # Get target chain
        chain = manager.get_sub_chain(chain_name)
        if not chain:
            raise HTTPException(status_code=404, detail=f"Chain '{chain_name}' not found")
        
        # Add event to chain
        event_data = request.model_dump()
        
        # 1. Cryptographic validation using SignatureVerifier
        # This performs canonicalization and Ed25519/ECDSA verification
        if not verifier.verify_event_signature(event_data, request.sender):
            logger.warning(
                "Secure event signature verification failed",
                chain=chain_name,
                sender=request.sender,
                entity_id=request.entity_id
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cryptographic signature verification failed. Event integrity cannot be guaranteed."
            )

        # 2. Add verified event to chain
        event_hash = chain.add_event(event_data)

        logger.audit(
            action="submit_secure",
            resource="event",
            success=True,
            chain=chain_name,
            entity_id=request.entity_id
        )

        return SecureEventResponse(
            status="committed", event_hash=event_hash, timestamp=time.time()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Secure event submission failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
