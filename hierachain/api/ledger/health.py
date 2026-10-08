"""API Ledger — health-check and network-ping endpoints."""

import time
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.consensus.ordering.types import OrderingStatus
from hierachain.hierarchical.hierarchy_manager import HierarchyManager

router = APIRouter(tags=["HieraChain"])


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}


@router.get("/ready")
async def readiness_check(
    manager: HierarchyManager = Depends(get_hierarchy_manager),
):
    """Report ready only after every registered ordering service finishes recovery."""
    ready = all(
        getattr(getattr(chain, "ordering_service", None), "status", None)
        == OrderingStatus.ACTIVE
        for chain in manager.get_all_sub_chains().values()
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if ready else "not_ready",
            "timestamp": time.time(),
        },
    )


@router.get("/network/ping/{target_id}")
async def network_ping(target_id: str):
    from hierachain.api.context import get_p2p_client

    p2p_client = get_p2p_client()
    if not p2p_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="P2P network layer is not initialized or disabled"
        )

    success = await p2p_client.send_direct(
        target_id,
        {
            "type": "ping",
            "timestamp": time.time(),
            "nonce": uuid_lib.uuid4().hex
        }
    )

    if not success:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "detail": f"Failed to send ping to {target_id}"}
        )

    return {"success": True, "target": target_id, "timestamp": time.time()}
