"""API Ledger — health-check and network-ping endpoints."""

import time
import uuid as uuid_lib
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["HieraChain"])


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}


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
