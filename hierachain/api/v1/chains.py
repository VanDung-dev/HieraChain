"""API v1 — chain management endpoints.

List chains, get chain stats, and create sub-chains.
"""

import re
import os
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from hierachain.api.v1.schemas import ChainInfoResponse, ChainStatsResponse
from hierachain.api.v1.depds import get_hierarchy_manager
from hierachain.core.blockchain import Blockchain
from hierachain.hierarchical.main_chain import MainChain
from hierachain.hierarchical.sub_chain import SubChain
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.sanitization import sanitize_string
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.security.secure_logging import SecureLogger

router = APIRouter(tags=["HieraChain"])
api_logger = SecureLogger("hierachain.api.v1")


def get_chain_by_name(manager: HierarchyManager, chain_name: str) -> Blockchain | None:
    if chain_name == "main_chain":
        return manager.get_main_chain()
    return manager.get_sub_chain(chain_name)


def validate_chain_exists(
    manager: HierarchyManager,
    chain_name: str
) -> SubChain:
    sub_chain = manager.get_sub_chain(chain_name)
    if not sub_chain:
        raise HTTPException(
            status_code=404, detail=f"Sub-chain '{chain_name}' not found"
        )
    return sub_chain


@router.get(
    "/chains",
    response_model=list[ChainInfoResponse],
    dependencies=[Depends(require_chain_access)]
)
async def list_chains(manager: HierarchyManager = Depends(get_hierarchy_manager)):
    try:
        chains = []

        main_chain = manager.get_main_chain()
        if main_chain:
            chains.append(ChainInfoResponse(
                name="main_chain",
                type="main",
                block_count=len(getattr(main_chain, 'chain', [])),
                latest_block_hash=(
                    main_chain.get_latest_block().hash
                    if getattr(main_chain, 'chain', None) else None
                )
            ))

        for sub_chain_name, sub_chain in manager.get_all_sub_chains().items():
            chains.append(ChainInfoResponse(
                name=sub_chain_name,
                type="sub",
                block_count=len(getattr(sub_chain, 'chain', [])),
                latest_block_hash=(
                    sub_chain.get_latest_block().hash
                    if getattr(sub_chain, 'chain', None) else None
                )
            ))

        return chains
    except Exception as e:
        api_logger.error("Failed to list chains", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to list chains. An internal error has occurred."
        ) from e


def _calculate_basic_chain_stats(chain) -> tuple[int, int]:
    chain_blocks = getattr(chain, 'chain', [])
    total_blocks = len(chain_blocks)
    total_events = sum(len(getattr(block, 'events', [])) for block in chain_blocks)
    return total_blocks, total_events


def _get_extended_chain_stats(
    manager: HierarchyManager,
    chain_name: str,
    total_blocks: int
) -> tuple[int | None, int | None]:
    if chain_name == "main_chain":
        proof_count = max(0, total_blocks - 1)
        registered_sub_chains = len(manager.get_all_sub_chains())
        return proof_count, registered_sub_chains

    return None, None


@router.get(
    "/chains/{chain_name}/stats",
    response_model=ChainStatsResponse,
    dependencies=[Depends(require_chain_access)]
)
async def get_chain_stats(
    chain_name: str,
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    try:
        chain = get_chain_by_name(manager, chain_name)
        if not chain:
            raise HTTPException(
                status_code=404, detail=f"Chain '{chain_name}' not found"
            )

        total_blocks, total_events = _calculate_basic_chain_stats(chain)
        metrics = _get_extended_chain_stats(manager, chain_name, total_blocks)
        proof_count, registered_sub_chains = metrics

        return ChainStatsResponse(
            chain_name=chain_name,
            total_blocks=total_blocks,
            total_events=total_events,
            proof_count=proof_count,
            registered_sub_chains=registered_sub_chains
        )
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            "Failed to get chain stats", error=str(e), chain_name=chain_name
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to get chain stats. An internal error has occurred."
        ) from e


def _ensure_main_chain(manager: HierarchyManager) -> None:
    """Ensures the main chain is initialized in the manager."""
    main_chain = manager.get_main_chain()
    if not main_chain:
        main_chain = MainChain()
        manager.set_main_chain(main_chain)


def _register_new_sub_chain(
    manager: HierarchyManager, safe_chain_name: str, safe_chain_type: str
) -> JSONResponse | None:
    """Attempts to add a new sub-chain to the manager. Returns conflict response if it exists."""
    sub_chain = SubChain(name=safe_chain_name, domain_type=safe_chain_type)
    try:
        manager.add_sub_chain(safe_chain_name, sub_chain)
        return None
    except ValueError as ve:
        api_logger.info(
            "Sub-chain already exists", chain_name=safe_chain_name, error=str(ve)
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "message": f"Sub-chain '{safe_chain_name}' already exists",
                "chain_name": safe_chain_name,
            },
        )


@router.post(
    "/chains/{chain_name}/create", dependencies=[Depends(require_chain_access)]
)
async def create_sub_chain(
    chain_name: str,
    chain_type: str = "generic",
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    if not re.match(r'^[a-zA-Z0-9_\-]+$', chain_name):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid chain identifier '{sanitize_string(chain_name)}'. "
                "Only alphanumeric, underscore, and hyphen are allowed."
            )
        )
    safe_chain_type = sanitize_string(chain_type)
    safe_chain_name = os.path.basename(chain_name)

    try:
        _ensure_main_chain(manager)

        if manager.get_sub_chain(safe_chain_name):
            api_logger.audit(
                action="create",
                resource="sub_chain",
                success=True,
                chain_name=safe_chain_name,
                chain_type=safe_chain_type,
                note="already_exists",
            )
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content={
                    "success": True,
                    "message": f"Sub-chain '{chain_name}' created successfully",
                    "chain_name": chain_name
                }
            )

        conflict_response = _register_new_sub_chain(manager, safe_chain_name, safe_chain_type)
        if conflict_response:
            return conflict_response

        api_logger.audit(
            action="create",
            resource="sub_chain",
            success=True,
            chain_name=safe_chain_name,
            chain_type=safe_chain_type,
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "message": f"Sub-chain '{chain_name}' created successfully",
                "chain_name": chain_name
            }
        )
    except ValueError as e:
        if "already exists" in str(e):
            api_logger.warning(
                "Attempted to create existing sub-chain", chain_name=chain_name
            )
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content={
                    "success": True,
                    "message": f"Sub-chain '{chain_name}' created successfully",
                    "chain_name": chain_name
                }
            )
        raise
    except Exception as e:
        api_logger.error(
            "Failed to create sub-chain", error=str(e), chain_name=chain_name
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create sub-chain. An internal error has occurred."
        ) from e
