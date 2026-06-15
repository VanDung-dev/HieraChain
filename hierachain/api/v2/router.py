"""API v2 — router composition.

Aggregates all v2 endpoint modules under the /api/v2 prefix.
"""

from fastapi import APIRouter

from hierachain.api.v2.health import router as health_router
from hierachain.api.v2.channels import router as channels_router
from hierachain.api.v2.private_data import router as private_data_router
from hierachain.api.v2.contracts import router as contracts_router
from hierachain.api.v2.organizations import router as organizations_router

v2_router = APIRouter(prefix="/api/v2", tags=["HieraChain-v2"])
v2_router.include_router(health_router)
v2_router.include_router(channels_router)
v2_router.include_router(private_data_router)
v2_router.include_router(contracts_router)
v2_router.include_router(organizations_router)
