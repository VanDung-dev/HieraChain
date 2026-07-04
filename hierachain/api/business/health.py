"""API business — health-check endpoint."""

import time
from fastapi import APIRouter

router = APIRouter(tags=["HieraChain-business"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "business",
        "timestamp": time.time()
    }
