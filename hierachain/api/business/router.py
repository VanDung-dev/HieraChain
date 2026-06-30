"""API business — router composition.

Aggregates all business endpoint modules under the /api/business prefix.
"""

from fastapi import APIRouter

from hierachain.api.business.health import router as health_router
from hierachain.api.business.channels import router as channels_router
from hierachain.api.business.private_data import router as private_data_router
from hierachain.api.business.contracts import router as contracts_router
from hierachain.api.business.organizations import router as organizations_router

business_router = APIRouter(prefix="/api/business", tags=["HieraChain-business"])
business_router.include_router(health_router)
business_router.include_router(channels_router)
business_router.include_router(private_data_router)
business_router.include_router(contracts_router)
business_router.include_router(organizations_router)
