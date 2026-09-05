"""
FastAPI server for HieraChain Ledger

This module implements the REST API server for the HieraChain Ledger
The Ledger implements a hierarchical structure where the Main Chain
only stores proofs from Sub-Chains.

The server uses FastAPI for high performance and includes proper
error handling, CORS support, and comprehensive logging.
"""

import os
import logging
import traceback
from typing import Any, cast
from fastapi import (
    FastAPI, HTTPException, Depends, Request
)
from fastapi.middleware.cors import CORSMiddleware
import warnings
from contextlib import asynccontextmanager

from hierachain.config.logging import LOGGING_CONFIG

from hierachain.api.ledger.router import ledger_router
from hierachain.api.business.router import business_router
from hierachain.api.admin.endpoints import router as admin_router
from hierachain.api.websocket.manager import ws_manager
from hierachain.api.middleware import (
    add_security_headers, add_payload_limit, add_rate_limit,
    add_request_logging,
)
from hierachain.api.graphql_handler import _register_graphql_router
from hierachain.config.settings import get_settings
from hierachain.security.verify.api_key_verifier import APIKeyVerifier
from hierachain.network.network_client import NetworkClient, NetworkClientConfig

from hierachain.api.context import set_p2p_client, get_p2p_client

logger = logging.getLogger(__name__)

p2p_client: NetworkClient | None = None

EXEMPT_PATHS = {
    "/",
    "/api/ledger/health",
    "/api/business/health",
    "/api/admin/status",
    "/api/admin/verify-identity",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/ws",
    "/ws/status",
}


async def _start_p2p_network_layer(settings) -> None:
    """Helper to initialize and start the P2P network layer if enabled."""
    global p2p_client
    p2p_config = settings.get_p2p_config()

    if not p2p_config["enabled"]:
        logger.info("P2P network layer is DISABLED")
        return

    from hierachain.security.identity_loader import load_node_identity
    node_identity = load_node_identity()

    transport_secret = None
    transport_public = None
    if node_identity:
        transport_secret = node_identity.transport_secret_key
        transport_public = node_identity.transport_public_key
        logger.info("Loaded transport keys for node identity: %s", node_identity.node_id)
    else:
        logger.warning("No fixed node identity found, will use ephemeral transport keys")

    config = NetworkClientConfig(
        enabled=True,
        node_id=settings.NODE_ID,
        host=p2p_config["host"],
        port=p2p_config["port"],
        seed_nodes=p2p_config["seed_nodes"],
        transport_secret_key=transport_secret,
        transport_public_key=transport_public
    )
    client_instance = NetworkClient(config)
    success = await client_instance.start()
    p2p_client = client_instance
    set_p2p_client(client_instance)
    if success:
        logger.info("P2P network layer STARTED for node %s", settings.NODE_ID)
    else:
        logger.error("Failed to start P2P network layer")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting HieraChain API server...")

    await ws_manager.start()
    logger.info("WebSocket manager started")

    settings = get_settings()
    await _start_p2p_network_layer(settings)

    if settings.AUTH_ENABLED:
        logger.info("Global API Authentication ENFORCED")
    else:
        logger.warning("Global API Authentication DISABLED")

    _check_cors_config(settings)

    yield

    logger.info("Shutting down HieraChain API server...")

    await ws_manager.stop()
    logger.info("WebSocket manager stopped")

    current_p2p = get_p2p_client()
    if current_p2p:
        await current_p2p.stop()
        set_p2p_client(None)
        logger.info("P2P network layer stopped")


def _check_cors_config(settings) -> None:
    env = getattr(settings, "ENV", "dev")
    if env != "product":
        return

    if settings.CORS_ALLOW_ALL:
        logger.warning(
            "SECURITY: CORS_ALLOW_ALL is True in production. "
            "This allows any origin to access the API. "
            "Set HRC_CORS_ALLOW_ALL=false and configure "
            "HRC_CORS_ORIGINS for production."
        )

    if not settings.CORS_ALLOW_ALL and not settings.CORS_ORIGINS:
        logger.warning(
            "SECURITY: CORS_ALLOW_ALL is False but "
            "CORS_ORIGINS is empty in production. "
            "No cross-origin requests will be allowed. "
            "Set HRC_CORS_ORIGINS to your frontend domains."
        )


def register_exception_handlers(fast_app: FastAPI, settings) -> None:
    @fast_app.exception_handler(Exception)
    async def global_exception_handler(_request, exc):
        logger.error(f"Unhandled exception: {str(exc)}")
        is_debug = (
            settings.LOG_LEVEL == "DEBUG" and
            getattr(settings, "ENV", "dev") != "product"
        )
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "detail": str(exc) if is_debug else "Contact system administrator"
            }
        )

    @fast_app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc):
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP error",
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )

    @fast_app.exception_handler(RecursionError)
    async def recursion_error_handler(_request, _exc):
        from starlette.responses import JSONResponse
        logger.warning("RecursionError detected - possible JSON bomb attempt")
        return JSONResponse(
            status_code=422,
            content={
                "error": "Unprocessable Entity",
                "message": "Input data too complex or deeply nested",
                "status_code": 422
            }
        )


def _register_api_router(fast_app: FastAPI, router, version: str):
    try:
        fast_app.include_router(router)
        logger.debug(f"API {version} router included successfully")
    except ImportError:
        logger.warning(f"API {version} router not available")


def _register_websocket_router(fast_app: FastAPI):
    try:
        from hierachain.api.websocket.endpoints import router as ws_router
        fast_app.include_router(ws_router)
        logger.info("WebSocket router registered at /ws")
    except Exception as exc:
        logger.error("WebSocket router registration FAILED: %s\n%s", exc, traceback.format_exc())


def _register_root_endpoint(fast_app: FastAPI):
    @fast_app.get("/")
    async def root():
        return {
            "name": "HieraChain Ledger API",
            "description": "REST API for enterprise blockchain applications",
            "docs_url": "/docs",
        }


def _register_metrics_endpoint(fast_app: FastAPI) -> None:
    try:
        import prometheus_client
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from fastapi import Response

        @fast_app.get("/metrics", include_in_schema=False)
        async def metrics_endpoint() -> Response:
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )

        logger.info("Prometheus /metrics endpoint registered")
    except ImportError:
        logger.warning(
            "prometheus-client not installed. "
            "Install it with: pip install prometheus-client==0.21.1"
        )


def register_routers(fast_app: FastAPI):
    _register_api_router(fast_app, ledger_router, "ledger")
    _register_api_router(fast_app, business_router, "business")
    _register_api_router(fast_app, admin_router, "admin")
    _register_websocket_router(fast_app)
    _register_graphql_router(fast_app)
    _register_root_endpoint(fast_app)


def _add_cors_middleware(fast_app: Any, cors_config: dict[str, Any]) -> None:
    """Configure CORS middleware on application instance."""
    fast_app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config.get("allow_origins", ["*"]),
        allow_credentials=cors_config.get("allow_credentials", False),
        allow_methods=cors_config.get("allow_methods", ["*"]),
        allow_headers=cors_config.get("allow_headers", ["*"]),
    )


def create_app() -> FastAPI:
    settings = get_settings()
    api_config = settings.get_api_config()

    verifier = APIKeyVerifier(settings.get_auth_config()) if settings.AUTH_ENABLED else None

    async def auth_dependency(request: Request):
        if not settings.AUTH_ENABLED:
            return None
        if request.url.path in EXEMPT_PATHS:
            return {"user_id": "system", "app_details": {"name": "Exempt"}}
        return await verifier(request)  # type: ignore

    dependencies = [Depends(auth_dependency)] if settings.AUTH_ENABLED else []

    fast_app = FastAPI(
        title="HieraChain Ledger API",
        description=(
            "REST API for the HieraChain Ledger - "
            "A general-purpose blockchain system "
            "for enterprise applications"
        ),
        version=api_config["version"],
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        dependencies=dependencies,
    )

    cors_config = settings.get_cors_config()
    _add_cors_middleware(fast_app, cors_config)

    add_security_headers(fast_app, settings.env in ("dev", "development"))
    add_request_logging(fast_app)
    add_rate_limit(fast_app, settings, EXEMPT_PATHS)
    add_payload_limit(fast_app)

    register_routers(fast_app)

    if getattr(settings, "METRICS_ENABLED", False):
        _register_metrics_endpoint(fast_app)

    register_exception_handlers(fast_app, settings)

    return fast_app


warnings.filterwarnings("ignore", category=UserWarning, module="requests")

app = create_app()


def run_server():
    import uvloop
    uvloop.install()

    import uvicorn
    settings = get_settings()
    api_config = settings.get_api_config()
    is_debug = settings.LOG_LEVEL == "DEBUG"

    uvicorn.run(
        "hierachain.api.server:app",
        host=api_config["host"],
        port=cast(int, api_config["port"]),
        reload=is_debug,
        log_level="info" if not is_debug else "debug",
        log_config=LOGGING_CONFIG,
        server_header=False,
        timeout_keep_alive=int(os.getenv("HRC_API_TIMEOUT_KEEP_ALIVE", "15")),
        limit_concurrency=int(os.getenv("HRC_API_LIMIT_CONCURRENCY", "500")),
        headers=[("Server", "HieraChain")],
        proxy_headers=True,
        forwarded_allow_ips=api_config.get("trusted_proxies", "127.0.0.1")
    )


if __name__ == "__main__":
    run_server()
