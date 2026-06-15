"""API v2 — health-check endpoint."""

import time
from fastapi import APIRouter

router = APIRouter(tags=["HieraChain-v2"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "v2",
        "timestamp": time.time()
    }
