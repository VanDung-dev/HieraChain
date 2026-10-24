from typing import Any

from fastapi import Depends, HTTPException

from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.verify.api_key_verifier import (
    require_chain_access,
    require_event_access,
    require_proof_access,
)


def authenticated_user_id(context: object) -> str | None:
    user_id = context.get("user_id") if isinstance(context, dict) else None
    return user_id if isinstance(user_id, str) and user_id else None


def enforce_chain_access(
    manager: HierarchyManager, chain_name: str, context: object, permission: str = "read",
) -> None:
    if not manager.can_access_chain(chain_name, authenticated_user_id(context), permission):
        raise HTTPException(status_code=403, detail="Access to this chain is not permitted")


def require_chain_read(
    chain_name: str, context: dict[str, Any] = Depends(require_chain_access),
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> None:
    enforce_chain_access(manager, chain_name, context)


def require_chain_write(
    chain_name: str, context: dict[str, Any] = Depends(require_event_access),
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> None:
    enforce_chain_access(manager, chain_name, context, "write")


def require_chain_proof(
    chain_name: str, context: dict[str, Any] = Depends(require_proof_access),
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> None:
    enforce_chain_access(manager, chain_name, context, "proofs")
