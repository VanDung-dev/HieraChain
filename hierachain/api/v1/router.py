"""API v1 — router composition.

Aggregates all v1 endpoint modules under the /api/v1 prefix.
"""

from fastapi import APIRouter

from hierachain.api.v1.health import router as health_router
from hierachain.api.v1.chains import router as chains_router
from hierachain.api.v1.events import router as events_router
from hierachain.api.v1.proofs import router as proofs_router
from hierachain.api.v1.entities import router as entities_router
from hierachain.api.v1.blocks import router as blocks_router

v1_router = APIRouter(prefix="/api/v1", tags=["HieraChain"])
v1_router.include_router(health_router)
v1_router.include_router(chains_router)
v1_router.include_router(events_router)
v1_router.include_router(proofs_router)
v1_router.include_router(entities_router)
v1_router.include_router(blocks_router)
