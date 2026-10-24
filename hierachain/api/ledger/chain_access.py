from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from hierachain.api.ledger.access import authenticated_user_id
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.verify.api_key_verifier import (
    ResourcePermissionChecker,
    require_chain_access,
)

router = APIRouter(tags=["HieraChain"])


class ChainAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permissions: list[Literal["read", "write", "proofs"]] = Field(min_length=1)


def require_chain_management(
    context: dict[str, Any] = Depends(require_chain_access),
) -> dict[str, Any]:
    if authenticated_user_id(context) is None or not ResourcePermissionChecker.has_permission(context, "chains:manage"):
        raise HTTPException(status_code=403, detail="Chain assignments require chains:manage permission")
    return context


@router.get("/chains/{chain_name}/organizations", dependencies=[Depends(require_chain_management)])
def get_chain_organizations(
    chain_name: str, manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> dict[str, Any]:
    if manager.get_sub_chain(chain_name) is None:
        raise HTTPException(status_code=404, detail="Sub-chain not found")
    grants = manager.get_chain_access(chain_name)
    return {"chain_name": chain_name, "managed": grants is not None, "organizations": grants or {}}


@router.put("/chains/{chain_name}/organizations/{org_id}", dependencies=[Depends(require_chain_management)])
def assign_chain_organization(
    chain_name: str, org_id: str, request: ChainAccessRequest,
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> dict[str, Any]:
    if not manager.assign_organization_to_chain(org_id, chain_name, permissions=list(request.permissions)):
        raise HTTPException(status_code=404, detail="Organization or sub-chain not found")
    return {"success": True, "chain_name": chain_name, "org_id": org_id, "permissions": request.permissions}


@router.delete("/chains/{chain_name}/organizations/{org_id}", dependencies=[Depends(require_chain_management)])
def revoke_chain_organization(
    chain_name: str, org_id: str, manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> dict[str, Any]:
    if not manager.revoke_organization_from_chain(org_id, chain_name):
        raise HTTPException(status_code=404, detail="Chain assignment not found")
    return {"success": True, "chain_name": chain_name, "org_id": org_id}
