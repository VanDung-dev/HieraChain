"""
FastAPI server for HieraChain Ledger

This module implements the REST API server for the HieraChain Ledger
The Ledger implements a hierarchical structure where the Main Chain only stores 
proofs from Sub-Chains.

The server uses FastAPI for high performance and includes proper error handling,
CORS support, and comprehensive logging.
"""

import uvicorn
import logging
import time
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from hierachain.api.v1.endpoints import router as v1_router
from hierachain.api.v2.endpoints import router as v2_router
from hierachain.api.v3.endpoints import router as v3_router
from hierachain.config.settings import get_settings
from hierachain.security.verify.api_key_verifier import APIKeyVerifier

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting HieraChain API server...")
    
    # Log authentication status on startup
    settings = get_settings()
    if settings.AUTH_ENABLED:
        logger.info("Global API Authentication ENFORCED")
    else:
        logger.warning("Global API Authentication DISABLED")
    yield
    # Shutdown
    logger.info("Shutting down HieraChain API server...")


def add_security_headers(fast_app: FastAPI):
    """Add security headers middleware to the application"""
    @fast_app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        # Prevent MIME-sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent Clickjacking (protects Swagger UI)
        response.headers["X-Frame-Options"] = "DENY"
        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Prevent caching of sensitive data
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        
        # Hide Server Information
        if "server" in response.headers:
            del response.headers["server"]
        response.headers["Server"] = "HieraChain"

        # Allow Swagger UI to work properly
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            # Relaxed CSP for documentation pages
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com"
            )
        else:
            # Strict CSP for API endpoints
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        
        return response


def add_payload_limit(fast_app: FastAPI):
    """Add payload size limit middleware to the application"""
    @fast_app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        # 5 MB limit
        max_size = 5 * 1024 * 1024
        content_length = request.headers.get("content-length")

        # Check limit only for methods that typically have payloads
        if (request.method in ("POST", "PUT", "PATCH") and 
            content_length and int(content_length) > max_size):
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
        is_debug = settings.LOG_LEVEL == "DEBUG"
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


def register_routers(fast_app: FastAPI, api_config):
    """Register API routers and root endpoint"""
    # Try to include v1 router
    try:
        fast_app.include_router(v1_router)
        logger.debug("API v1 router included successfully")
    except ImportError:
        logger.warning("API v1 router not available")
    
    # Try to include v2 router
    try:
        fast_app.include_router(v2_router)
        logger.debug("API v2 router included successfully")
    except ImportError:
        logger.warning("API v2 router not available")

    # Try to include v3 router
    try:
        fast_app.include_router(v3_router)
        logger.debug("API v3 router included successfully")
    except ImportError:
        logger.warning("API v3 router not available")
    
    @fast_app.get("/")
    async def root():
        """Root endpoint with API information"""
        return {
            "name": "HieraChain Ledger API",
            "description": "REST API for enterprise blockchain applications",
            "docs_url": "/docs",
        }


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
        auth_dependency = lambda: None

    dependencies = [Depends(auth_dependency)] if settings.AUTH_ENABLED else []
    
    # Create FastAPI app
    fast_app = FastAPI(
        title="HieraChain Ledger API",
        description="REST API for the HieraChain Ledger - A general-purpose blockchain system for enterprise applications",
        version=api_config["version"],
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        dependencies=dependencies
    )

    # Add CORS middleware
    fast_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify allowed origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add Middlewares
    add_security_headers(fast_app)
    add_payload_limit(fast_app)
    add_rate_limit(fast_app, settings)

    # Register Routers and Root Endpoint
    register_routers(fast_app, api_config)

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