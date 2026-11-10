"""API Ledger — event submission endpoint.

Add business events to a sub-chain with optional off-chain
(IPFS) storage for large payloads.
"""

import re
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from hierachain.api.ledger.access import require_chain_write
from hierachain.api.ledger.depds import get_hierarchy_manager
from hierachain.api.ledger.schemas import EventRequest, EventResponse
from hierachain.api.storage.endpoint_helpers import process_event_details
from hierachain.api.websocket.manager import ws_manager
from hierachain.config.settings import get_settings
from hierachain.consensus.ordering.types import OrderingBackpressureError
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.security.sanitization import sanitize_dict, sanitize_string
from hierachain.security.secure_logging import SecureLogger
from hierachain.security.verify.api_key_verifier import require_event_access
from hierachain.security.verify.signature_verifier import SignatureVerifier

router = APIRouter(tags=["HieraChain"])
api_logger = SecureLogger("hierachain.api.ledger")
signature_verifier = SignatureVerifier()


def _verify_request_signature(event_request: EventRequest) -> None:
    if not event_request.signature:
        if get_settings().env == "production":
            raise HTTPException(
                status_code=422,
                detail="Signed events are required in production.",
            )
        return
    if not event_request.sender:
        raise HTTPException(
            status_code=422,
            detail="A sender is required for a signed event.",
        )
    signed_payload = event_request.model_dump(exclude_none=True)
    assert isinstance(event_request.sender, str)
    if not signature_verifier.verify_event_signature(signed_payload, event_request.sender):
        raise HTTPException(
            status_code=422,
            detail="Cryptographic signature verification failed.",
        )


def _resolve_submitter(auth_context: dict[str, Any]) -> str:
    user_id = auth_context.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=403, detail="Authenticated user is not registered")
    return user_id


def _build_event_data(
    event_request: EventRequest,
    inline_details: dict | None,
    cid_info: dict | None,
    submitted_by: str | None = None,
) -> dict:
    safe_entity_id = sanitize_string(event_request.entity_id)
    safe_event_type = sanitize_string(event_request.event_type)
    safe_details = sanitize_dict(inline_details) if inline_details else None

    event: dict = {
        "entity_id": safe_entity_id,
        "event": safe_event_type,
        "event_type": safe_event_type,
        "timestamp": time.time(),
        "submitted_by": submitted_by or event_request.sender,
        "sender": event_request.sender,
        "signature": event_request.signature,
    }

    if event_request.signature:
        event["signature_content"] = event_request.model_dump(
            exclude_none=True, exclude={"sender", "signature"}
        )

    if cid_info:
        event["details_cid"] = cid_info["cid"]
        event["details_nonce"] = cid_info["nonce"]
        if cid_info.get("metadata"):
            event["details_metadata"] = cid_info["metadata"]
    else:
        event["details"] = safe_details or {}

    return event


def _log_event_success(
    chain_name: str,
    safe_entity_id: str,
    cid_info: dict | None
) -> None:
    if cid_info:
        api_logger.info(
            "Event using off-chain storage",
            chain_name=chain_name,
            cid=cid_info["cid"],
            entity_id=safe_entity_id
        )

    api_logger.audit(
        action="add_event",
        resource="sub_chain",
        success=True,
        chain_name=chain_name,
        entity_id=safe_entity_id,
        storage_type="offchain" if cid_info else "onchain"
    )


@router.post(
    "/chains/{chain_name}/events",
    response_model=EventResponse,
    dependencies=[Depends(require_chain_write)]
)
async def add_event(
    chain_name: str,
    event_request: EventRequest,
    background_tasks: BackgroundTasks,
    auth_context: dict[str, Any] = Depends(require_event_access),
    manager: HierarchyManager = Depends(get_hierarchy_manager)
):
    if not re.match(r"^[a-zA-Z0-9_-]+$", chain_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid sub-chain name format. Only alphanumeric, dashes, and underscores are allowed."
        )

    sub_chain = manager.get_sub_chain(chain_name)
    if not sub_chain:
        raise HTTPException(
            status_code=404, detail=f"Sub-chain '{chain_name}' not found"
        )

    _verify_request_signature(event_request)
    submitted_by = _resolve_submitter(auth_context)

    inline_details, cid_info = process_event_details(
        event_request,
        background_tasks=background_tasks
    )

    event = _build_event_data(event_request, inline_details, cid_info, submitted_by)

    try:
        event_id = sub_chain.add_event(event)
    except OrderingBackpressureError as exc:
        raise HTTPException(status_code=503, detail={
            "message": str(exc), "event_id": exc.event_id, "journaled": exc.journaled,
        }) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _log_event_success(chain_name, event["entity_id"], cid_info)
    await ws_manager.broadcast_event(chain_name, {**event, "event_id": event_id})

    return EventResponse(
        success=True,
        message=f"Event added to chain '{chain_name}'" + (
            " (off-chain storage)" if cid_info else ""
        ),
        event_id=event_id
    )


@router.post(
    "/channels/{channel_id}/organizations/{org_id}/events",
    response_model=EventResponse,
)
async def add_channel_event(
    channel_id: str,
    org_id: str,
    event_request: EventRequest,
    background_tasks: BackgroundTasks,
    auth_context: dict[str, Any] = Depends(require_event_access),
    manager: HierarchyManager = Depends(get_hierarchy_manager),
) -> EventResponse:
    channel = manager.get_channel(channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")

    user_id = auth_context.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=403, detail="Authenticated user is not registered")

    _verify_request_signature(event_request)

    inline_details, cid_info = process_event_details(
        event_request,
        background_tasks=background_tasks,
    )
    event = _build_event_data(event_request, inline_details, cid_info, user_id)

    try:
        accepted = channel.submit_event(event, org_id, submitter_user_id=user_id)
    except RuntimeError as exc:
        api_logger.error("Channel event persistence failed", channel_id=channel_id)
        raise HTTPException(status_code=503, detail="Channel event could not be persisted") from exc
    if not accepted:
        raise HTTPException(
            status_code=403,
            detail="User is not authorized to submit events to this channel",
        )

    api_logger.audit(
        action="add_event",
        resource="channel",
        success=True,
        channel_id=channel_id,
        org_id=org_id,
        entity_id=event["entity_id"],
    )
    await ws_manager.broadcast_event(channel_id, event)
    return EventResponse(
        success=True,
        message=f"Event added to channel '{channel_id}'",
    )
