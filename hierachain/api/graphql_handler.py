"""
GraphQL handler for HieraChain API server.

Provides GraphQL validation, query execution, and route registration
with security measures (rate limiting, depth checking, introspection control).
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from graphql import get_operation_ast, parse

from hierachain.api.graphql import security as graphql_security
from hierachain.api.graphql.schema import schema as graphql_schema
from hierachain.config.settings import get_settings
from hierachain.security.verify.api_key_verifier import ResourcePermissionChecker
from hierachain.serialization import loads_json

logger = logging.getLogger(__name__)


async def _validate_graphql_request(
    request: Request,
) -> tuple[bool, JSONResponse | None, dict | None]:
    client = request.client
    client_ip = "unknown"
    if client is not None:
        client_ip = client.host

    if not graphql_security.check_rate_limit(client_ip):
        return False, JSONResponse(
            status_code=429,
            content={"errors": [{"message": "Rate limit exceeded. Please try again later."}]}
        ), None

    try:
        body = loads_json(await request.body())
    except json.JSONDecodeError:
        return False, JSONResponse(
            status_code=400,
            content={"errors": [{"message": "Invalid JSON body"}]}
        ), None

    query = body.get("query", "")
    variables = body.get("variables", {})
    operation_name = body.get("operationName")

    settings = get_settings()
    is_production = settings.env == "production"

    if is_production and graphql_security.is_introspection_query(query):
        return False, JSONResponse(
            status_code=400,
            content={"errors": [{"message": "Introspection queries disabled in production"}]}
        ), None

    depth = graphql_security.get_query_depth(query)
    if depth > graphql_security.MAX_QUERY_DEPTH:
        return False, JSONResponse(
            status_code=400,
            content={"errors": [{"message": f"Query depth exceeds maximum of {graphql_security.MAX_QUERY_DEPTH} levels"}]}
        ), None

    complexity = graphql_security.estimate_complexity(query)
    if complexity > graphql_security.MAX_COMPLEXITY:
        return False, JSONResponse(
            status_code=400,
            content={"errors": [{"message": "Query complexity exceeds maximum allowed"}]}
        ), None

    return True, None, {"query": query, "variables": variables, "operation_name": operation_name}


async def _execute_graphql_query(
    query: str,
    variables: dict,
    operation_name: str | None,
    context_value: dict[str, Any] | None = None,
) -> tuple[dict, bool]:
    result = await graphql_schema.execute_async(
        query,
        variable_values=variables,
        operation_name=operation_name,
        context_value=context_value,
    )

    if result.errors:
        _settings = get_settings()
        is_debug = (
            _settings.LOG_LEVEL == "DEBUG"
            and _settings.env != "production"
        )
        for err in result.errors:
            logger.error(f"GraphQL schema error: {err.message}")
        error_messages = (
            [{"message": str(err.message)} for err in result.errors]
            if is_debug
            else [{"message": "An internal error occurred"}]
        )
        return {
            "data": result.data,
            "errors": error_messages
        }, True

    return {"data": result.data}, False


def _required_graphql_permissions(query: str, operation_name: str | None) -> set[str]:
    """Return the scopes needed by the selected GraphQL operation's root fields."""
    document = parse(query)
    operation = get_operation_ast(document, operation_name)
    if operation is None or operation.operation.value == "subscription":
        raise ValueError("A single query or mutation operation is required")

    fragments = {
        definition.name.value: definition
        for definition in document.definitions
        if definition.kind == "fragment_definition"
    }
    root_fields: set[str] = set()
    includes_nested_events = False

    def collect_fields(
        selection_set: Any,
        visited_fragments: set[str],
        at_root: bool,
    ) -> None:
        nonlocal includes_nested_events
        for selection in selection_set.selections:
            if selection.kind == "field":
                if at_root:
                    root_fields.add(selection.name.value)
                elif selection.name.value == "events":
                    includes_nested_events = True
                if selection.selection_set is not None:
                    collect_fields(
                        selection.selection_set, visited_fragments, at_root=False
                    )
            elif selection.kind == "inline_fragment":
                collect_fields(
                    selection.selection_set, visited_fragments, at_root=at_root
                )
            elif selection.kind == "fragment_spread":
                fragment_name = selection.name.value
                if fragment_name in visited_fragments:
                    continue
                fragment = fragments.get(fragment_name)
                if fragment is not None:
                    collect_fields(
                        fragment.selection_set,
                        visited_fragments | {fragment_name},
                        at_root=at_root,
                    )

    collect_fields(operation.selection_set, set(), at_root=True)
    if not root_fields:
        raise ValueError("The GraphQL operation has no root fields")

    required: set[str] = set()
    if operation.operation.value == "mutation":
        return {"events"}

    for field_name in root_fields:
        required.add("events" if field_name == "events" else "chains")
    if includes_nested_events:
        required.add("events")
    return required


async def _get_request_auth_context(request: Request) -> dict | None:
    """Return the API key context created by this app's configured verifier."""
    verifier = getattr(request.app.state, "auth_verifier", None)
    if verifier is None:
        if get_settings().AUTH_ENABLED:
            raise HTTPException(
                status_code=503,
                detail="Authentication verifier is unavailable.",
            )
        return None
    auth_context = await verifier(request)
    if auth_context is None and get_settings().AUTH_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Authentication verifier returned no auth context.",
        )
    return auth_context


def _register_graphql_router(fast_app):
    try:
        graphql_router = APIRouter()

        @graphql_router.post("/graphql")
        async def graphql_endpoint(request: Request):
            try:
                is_valid, error_response, parsed = await _validate_graphql_request(request)
                if not is_valid or parsed is None:
                    return error_response if error_response else JSONResponse(
                        status_code=400, content={"errors": [{"message": "Invalid request"}]}
                    )

                auth_context = await _get_request_auth_context(request)
                try:
                    required_permissions = _required_graphql_permissions(
                        parsed["query"], parsed["operation_name"]
                    )
                except (TypeError, ValueError):
                    return JSONResponse(
                        status_code=400,
                        content={"errors": [{"message": "Invalid GraphQL operation"}]},
                    )

                if auth_context is not None:
                    missing_permissions = sorted(
                        permission
                        for permission in required_permissions
                        if not ResourcePermissionChecker.has_permission(
                            auth_context, permission
                        )
                    )
                    if missing_permissions:
                        required = ", ".join(missing_permissions)
                        return JSONResponse(
                            status_code=403,
                            content={"errors": [{
                                "message": f"GraphQL operation requires '{required}' permission."
                            }]},
                        )

                response, is_error = await _execute_graphql_query(
                    parsed["query"],
                    parsed["variables"],
                    parsed["operation_name"],
                    context_value={"auth_context": auth_context},
                )
                status_code = 400 if is_error else 200

                return JSONResponse(status_code=status_code, content=response)
            except HTTPException as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"errors": [{"message": str(exc.detail)}]},
                )
            except Exception as exc:
                logger.error(f"GraphQL error: {exc}")
                return JSONResponse(
                    status_code=400,
                    content={"errors": [{"message": "An internal error occurred"}]}
                )

        fast_app.include_router(graphql_router)
        logger.debug("GraphQL endpoint included successfully")
    except Exception as e:
        logger.warning(f"GraphQL endpoint failed to load: {e}")
