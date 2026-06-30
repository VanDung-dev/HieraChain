"""API ledger — router composition.

Aggregates all ledger endpoint modules under the /api/ledger prefix.
"""

from fastapi import APIRouter

from hierachain.api.ledger.health import router as health_router
from hierachain.api.ledger.chains import router as chains_router
from hierachain.api.ledger.events import router as events_router
from hierachain.api.ledger.proofs import router as proofs_router
from hierachain.api.ledger.entities import router as entities_router
from hierachain.api.ledger.blocks import router as blocks_router

ledger_router = APIRouter(prefix="/api/ledger", tags=["HieraChain"])
ledger_router.include_router(health_router)
ledger_router.include_router(chains_router)
ledger_router.include_router(events_router)
ledger_router.include_router(proofs_router)
ledger_router.include_router(entities_router)
ledger_router.include_router(blocks_router)
