"""API v1 — entity tracing endpoint.

Trace an entity's events across the main chain and all sub-chains.
"""

from fastapi import APIRouter, Depends

from hierachain.api.v1.schemas import EntityTraceResponse
from hierachain.api.v1.depds import get_hierarchy_manager, get_entity_tracer
from hierachain.api.v1.chains import validate_chain_exists
from hierachain.hierarchical.hierarchy_manager import HierarchyManager
from hierachain.domains.generic.utils.entity_tracer import EntityTracer
from hierachain.security.sanitization import sanitize_string
from hierachain.security.verify.api_key_verifier import require_chain_access
from hierachain.api.storage.endpoint_helpers import (
    is_ipfs_enabled,
    resolve_multiple_events,
)

router = APIRouter(tags=["HieraChain"])


def _extract_events_for_specific_chain(
    tracer: EntityTracer,
    safe_entity_id: str,
    chain_name: str
) -> list:
    trace_result = tracer.trace_entity_in_chain(safe_entity_id, chain_name)
    return trace_result.get("events", [])


def _extract_events_across_all_chains(
    tracer: EntityTracer,
    safe_entity_id: str
) -> list:
    trace_result = tracer.trace_entity_across_chains(safe_entity_id)
    events = []
    for chain_events in trace_result.values():
        events.extend(chain_events)
    return events


@router.get(
    "/entities/{entity_id}/trace",
    response_model=EntityTraceResponse,
    dependencies=[Depends(require_chain_access)]
)
async def trace_entity(
    entity_id: str,
    chain_name: str | None = None,
    resolve_cid: bool = False,
    manager: HierarchyManager = Depends(get_hierarchy_manager),
    tracer: EntityTracer = Depends(get_entity_tracer)
):
    safe_entity_id = sanitize_string(entity_id)

    if chain_name:
        validate_chain_exists(manager, chain_name)
        events = _extract_events_for_specific_chain(tracer, safe_entity_id, chain_name)
    else:
        events = _extract_events_across_all_chains(tracer, safe_entity_id)

    if resolve_cid and is_ipfs_enabled():
        events = await resolve_multiple_events(events, resolve=True)

    chain_names = list(set(event.get('chain', 'unknown') for event in events))

    return EntityTraceResponse(
        entity_id=safe_entity_id,
        chains=chain_names,
        events=events
    )
