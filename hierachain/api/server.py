"""
FastAPI server for HieraChain Ledger

This module implements the REST API server for the HieraChain Ledger
The Ledger implements a hierarchical structure where the Main Chain
only stores proofs from Sub-Chains.

The server uses FastAPI for high performance and includes proper
error handling, CORS support, and comprehensive logging.
"""

import uuid
import uvicorn
import logging
import time
from fastapi import (
    FastAPI, HTTPException, Depends, Request, APIRouter, Response
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import warnings
from contextlib import asynccontextmanager

from hierachain.config.logging import LOGGING_CONFIG

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
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, private"
        )
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
    """Simple in-memory rate limiter (single-node only)"""
    def __init__(self, requests_per_minute: int):
        self.store: dict = {}
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

    def remaining(self, ip: str) -> int:
        """Return remaining requests in the current window."""
        now = int(time.time())
        start, count = self.store.get(ip, (now, 0))
        if now - start > 60:
            return self.limit
        return max(0, self.limit - count)


class RedisRateLimiter:
    """
    Sliding-window rate limiter backed by Redis.

    Uses INCR + EXPIRE for atomicity. Works across multiple server processes
    and nodes sharing the same Redis instance.
    """
    def __init__(self, requests_per_minute: int, host: str, port: int, db: int):
        import redis as redis_lib
        self._redis = redis_lib.Redis(
            host=host, port=port, db=db,
            socket_connect_timeout=2, socket_timeout=2, decode_responses=True
        )
        self.limit = requests_per_minute

    def _key(self, ip: str) -> str:
        window = int(time.time()) // 60
        return f"hrc:rl:{ip}:{window}"

    def is_allowed(self, ip: str) -> bool:
        key = self._key(ip)
        try:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            count, _ = pipe.execute()
            return int(count) <= self.limit
        except Exception as exc:
            logger.warning("Redis rate-limiter error, allowing request: %s", exc)
            return True  # fail-open: don't block traffic if Redis is unavailable

    def remaining(self, ip: str) -> int:
        key = self._key(ip)
        try:
            count = int(self._redis.get(key) or 0)
            return max(0, self.limit - count)
        except Exception:
            return self.limit



def add_rate_limit(fast_app: FastAPI, settings) -> None:
    """Add rate limit middleware — memory or Redis backend."""
    if not settings.RATE_LIMIT_ENABLED:
        return

    rpm = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
    backend = getattr(settings, "RATE_LIMIT_BACKEND", "memory")

    if backend == "redis":
        limiter: RateLimiter | RedisRateLimiter = RedisRateLimiter(
            rpm,
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
        )
        logger.info("Rate limiter: Redis backend (%d rpm)", rpm)
    else:
        limiter = RateLimiter(rpm)
        logger.info("Rate limiter: in-memory backend (%d rpm)", rpm)

    @fast_app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        
        if not limiter.is_allowed(client_ip):
            remaining = limiter.remaining(client_ip)
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(rpm),
                    "X-RateLimit-Remaining": str(remaining),
                },
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "status_code": 429,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rpm)
        response.headers["X-RateLimit-Remaining"] = str(limiter.remaining(client_ip))
        return response



def register_exception_handlers(fast_app: FastAPI, settings) -> None:
    """Register global exception handlers"""
    @fast_app.exception_handler(Exception)
    async def global_exception_handler(_request, exc):
        logger.error(f"Unhandled exception: {str(exc)}")
        is_debug = (
            settings.LOG_LEVEL == "DEBUG" and
            getattr(settings, "ENV", "dev") != "product"
        )
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
                return JSONResponse(
                    status_code=400,
                    content={"errors": [{"message": "An internal error occurred"}]}
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


def add_request_logging(fast_app: FastAPI) -> None:
    """
    Middleware that:
    - Generates a unique X-Request-ID for every request.
    - Logs method, path, status code, and latency in milliseconds.
    """
    @fast_app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        response = await call_next(request)

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "%s %s -> %s (%.2f ms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            request_id,
            extra={"request_id": request_id},
        )
        return response


def _register_metrics_endpoint(fast_app: FastAPI) -> None:
    """Register Prometheus /metrics endpoint (requires prometheus-client)."""
    try:
        import prometheus_client  # type: ignore[import]
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        @fast_app.get("/metrics", include_in_schema=False)
        async def metrics_endpoint() -> Response:
            """Prometheus metrics scrape endpoint."""
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
    add_request_logging(fast_app)

    # Register Routers and Root Endpoint
    register_routers(fast_app)

    # Register optional Prometheus /metrics endpoint
    if getattr(settings, "METRICS_ENABLED", False):
        _register_metrics_endpoint(fast_app)

    # Register Exception Handlers
    register_exception_handlers(fast_app, settings)

    return fast_app


# Suppress RequestsDependencyWarning
warnings.filterwarnings("ignore", category=UserWarning, module="requests")

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
        log_config=LOGGING_CONFIG,
        server_header=False,
        timeout_keep_alive=5,   # Mitigate Slowloris: low keep-alive timeout
        limit_concurrency=100,  # Limit concurrent connections
        headers=[("Server", "HieraChain")]  # Custom server header
    )


if __name__ == "__main__":
    run_server()
