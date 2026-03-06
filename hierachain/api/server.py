"""
FastAPI server for HieraChain Ledger

This module implements the REST API server for the HieraChain Ledger
The Ledger implements a hierarchical structure where the Main Chain
only stores proofs from Sub-Chains.

The server uses FastAPI for high performance and includes proper
error handling, CORS support, and comprehensive logging.
"""

import uvicorn
import logging
import time
from fastapi import FastAPI, HTTPException, Depends, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from hierachain.api.v1.endpoints import router as v1_router
from hierachain.api.v2.endpoints import router as v2_router
from hierachain.api.v3.endpoints import router as v3_router
from hierachain.api.websocket.endpoints import router as ws_router
from hierachain.api.websocket.manager import ws_manager
from hierachain.api.graphql.schema import schema as graphql_schema
from hierachain.config.settings import get_settings
from hierachain.security.verify.api_key_verifier import APIKeyVerifier

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting HieraChain API server...")
    
    # Start WebSocket manager
    await ws_manager.start()
    logger.info("WebSocket manager started")
    
    # Log authentication status on startup
    settings = get_settings()
    if settings.AUTH_ENABLED:
        logger.info("Global API Authentication ENFORCED")
    else:
        logger.warning("Global API Authentication DISABLED")

    # CORS safety checks for production
    _check_cors_config(settings)

    yield
    # Shutdown
    logger.info("Shutting down HieraChain API server...")
    
    # Stop WebSocket manager
    await ws_manager.stop()
    logger.info("WebSocket manager stopped")


def _check_cors_config(settings) -> None:
    """Log warnings if CORS configuration is unsafe for production."""
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


def _get_csp_for_docs(is_dev: bool) -> str:
    """Get Content-Security-Policy for documentation pages."""
    if is_dev:
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com"
        )
    return "default-src 'self'; script-src 'self'; style-src 'self'"


def _get_csp_for_api() -> str:
    """Get strict Content-Security-Policy for API endpoints."""
    return "default-src 'none'; frame-ancestors 'none'"


def _is_docs_path(path: str) -> bool:
    """Check if request path is for documentation pages."""
    return path in ("/docs", "/redoc", "/openapi.json")


def add_security_headers(fast_app: FastAPI, is_dev: bool):
    """Add security headers middleware to the application"""
    # Cache environment flag at registration time

    @fast_app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        
        # Set standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        
        # Hide Server Information
        if "server" in response.headers:
            del response.headers["server"]
        
        # Set CSP based on path
        path = request.url.path
        if _is_docs_path(path):
            response.headers["Content-Security-Policy"] = _get_csp_for_docs(is_dev)
        else:
            response.headers["Content-Security-Policy"] = _get_csp_for_api()
        
        return response


def add_payload_limit(fast_app: FastAPI):
    """Add payload size limit middleware to the application"""
    @fast_app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        # 5 MB limit
        max_size = 5 * 1024 * 1024
        content_length = request.headers.get("content-length")

        # Check limit only for methods that typically have payloads
        if (
            request.method in ("POST", "PUT", "PATCH")
            and content_length
            and int(content_length) > max_size
        ):
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Payload Too Large",
                    "message": f"Request body too large. Limit is {max_size} bytes",
                    "status_code": 413
                }
            )
            
        return await call_next(request)


class RateLimiter:
    """Simple in-memory rate limiter"""
    def __init__(self, requests_per_minute: int):
        self.store = {}
        self.limit = requests_per_minute

    def is_allowed(self, ip: str) -> bool:
        now = int(time.time())
        # Cleanup old entries every minute
        if now % 60 == 0:
            self.store = {k: v for k, v in self.store.items() if v[0] > now - 60}
        
        start, count = self.store.get(ip, (now, 0))
        
        # Reset window if expired
        if now - start > 60:
            self.store[ip] = (now, 1)
            return True
            
        if count >= self.limit:
            return False
            
        self.store[ip] = (start, count + 1)
        return True


def add_rate_limit(fast_app: FastAPI, settings):
    """Add rate limit middleware to the application"""
    if not settings.RATE_LIMIT_ENABLED:
        return
        
    limiter = RateLimiter(settings.RATE_LIMIT_REQUESTS_PER_MINUTE)
    
    @fast_app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        
        if not limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "status_code": 429
                }
            )
            
        return await call_next(request)


def register_exception_handlers(fast_app: FastAPI, settings):
    """Register global exception handlers"""
    @fast_app.exception_handler(Exception)
    async def global_exception_handler(_request, exc):
        logger.error(f"Unhandled exception: {str(exc)}")
        is_debug = settings.LOG_LEVEL == "DEBUG" and getattr(settings, "ENV", "dev") != "product"
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
    """Helper to register an API router with error handling."""
    try:
        fast_app.include_router(router)
        logger.debug(f"API {version} router included successfully")
    except ImportError:
        logger.warning(f"API {version} router not available")


def _register_websocket_router(fast_app: FastAPI):
    """Helper to register WebSocket router with error handling."""
    try:
        fast_app.include_router(ws_router)
        logger.debug("WebSocket router included successfully")
    except ImportError:
        logger.warning("WebSocket router not available")


def _register_graphql_router(fast_app: FastAPI):
    """Helper to register GraphQL router with error handling."""
    try:
        graphql_router = APIRouter()
        
        @graphql_router.post("/graphql")
        async def graphql_endpoint(request: Request):
            """GraphQL endpoint handler"""
            try:
                body = await request.json()
                query = body.get("query", "")
                variables = body.get("variables", {})
                operation_name = body.get("operationName")
                
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
                    return JSONResponse(
                        status_code=400,
                        content={
                            "data": result.data,
                            "errors": error_messages
                        }
                    )
                
                return {"data": result.data}
            except Exception as exc:
                logger.error(f"GraphQL error: {exc}")
                _settings = get_settings()
                is_debug = (
                    _settings.LOG_LEVEL == "DEBUG"
                    and getattr(_settings, "ENV", "dev") != "product"
                )
                error_msg = str(exc) if is_debug else "An internal error occurred"
                return JSONResponse(
                    status_code=400,
                    content={"errors": [{"message": error_msg}]}
                )
        
        fast_app.include_router(graphql_router)
        logger.debug("GraphQL endpoint included successfully")
    except Exception as e:
        logger.warning(f"GraphQL endpoint failed to load: {e}")


def _register_root_endpoint(fast_app: FastAPI):
    """Helper to register root endpoint."""
    @fast_app.get("/")
    async def root():
        """Root endpoint with API information"""
        return {
            "name": "HieraChain Ledger API",
            "description": "REST API for enterprise blockchain applications",
            "docs_url": "/docs",
        }


def register_routers(fast_app: FastAPI):
    """Register API routers and root endpoint"""
    _register_api_router(fast_app, v1_router, "v1")
    _register_api_router(fast_app, v2_router, "v2")
    _register_api_router(fast_app, v3_router, "v3")
    _register_websocket_router(fast_app)
    _register_graphql_router(fast_app)
    _register_root_endpoint(fast_app)


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    # Get settings
    settings = get_settings()
    api_config = settings.get_api_config()

    # Initialize implementation with settings
    if settings.AUTH_ENABLED:
        auth_dependency = APIKeyVerifier(settings.get_auth_config())
    else:
        # No-op dependency
        auth_dependency = lambda: None  # noqa: E731

    dependencies = [Depends(auth_dependency)] if settings.AUTH_ENABLED else []
    
    # Create FastAPI app
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
        dependencies=dependencies
    )

    # Add CORS middleware (driven by settings)
    cors_config = settings.get_cors_config()
    fast_app.add_middleware(
        CORSMiddleware,
        **cors_config
    )

    # Add Middlewares
    add_security_headers(fast_app, settings.ENV in ("dev", "development"))
    add_payload_limit(fast_app)
    add_rate_limit(fast_app, settings)

    # Register Routers and Root Endpoint
    register_routers(fast_app)

    # Register Exception Handlers
    register_exception_handlers(fast_app, settings)

    return fast_app


# Create app instance
app = create_app()


def run_server():
    """Run the server with uvicorn"""
    settings = get_settings()
    api_config = settings.get_api_config()
    is_debug = settings.LOG_LEVEL == "DEBUG"
    
    uvicorn.run(
        "hierachain.api.server:app",
        host=api_config["host"],
        port=api_config["port"],
        reload=is_debug,
        log_level="info" if not is_debug else "debug",
        server_header=False,
        timeout_keep_alive=5,  # Mitigate Slowloris: low keep-alive timeout
        limit_concurrency=100, # Limit concurrent connections
        headers=[("Server", "HieraChain")]  # Custom server header
    )


if __name__ == "__main__":
    run_server()
