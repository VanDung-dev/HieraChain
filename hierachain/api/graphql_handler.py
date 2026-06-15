"""
GraphQL handler for HieraChain API server.

Provides GraphQL validation, query execution, and route registration
with security measures (rate limiting, depth checking, introspection control).
"""

import json
import logging

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from hierachain.api.graphql.schema import schema as graphql_schema
from hierachain.api.graphql import security as graphql_security
from hierachain.config.settings import get_settings


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
        body = json.loads(await request.body())
    except json.JSONDecodeError:
        return False, JSONResponse(
            status_code=400,
            content={"errors": [{"message": "Invalid JSON body"}]}
        ), None

    query = body.get("query", "")
    variables = body.get("variables", {})
    operation_name = body.get("operationName")

    settings = get_settings()
    is_production = getattr(settings, "ENV", "dev") == "product"

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


def _execute_graphql_query(
    query: str,
    variables: dict,
    operation_name: str | None,
) -> tuple[dict, bool]:
    result = graphql_schema.execute(
        query,
        variable_values=variables,
        operation_name=operation_name
    )

    if result.errors:
        _settings = get_settings()
        is_debug = (
            _settings.LOG_LEVEL == "DEBUG"
            and getattr(_settings, "ENV", "dev") != "product"
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


def _register_graphql_router(fast_app):
    try:
        graphql_router = APIRouter()

        @graphql_router.post("/graphql")
        async def graphql_endpoint(request: Request):
            try:
                is_valid, error_response, parsed = await _validate_graphql_request(request)
                if not is_valid:
                    return error_response

                response, is_error = _execute_graphql_query(
                    parsed["query"], parsed["variables"], parsed["operation_name"]
                )
                status_code = 400 if is_error else 200

                return JSONResponse(status_code=status_code, content=response)
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
