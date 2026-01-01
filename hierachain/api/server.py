"""
FastAPI server for HieraChain Framework

This module implements the REST API server for the HieraChain Framework.
The framework implements a hierarchical structure where the Main Chain only stores 
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
from hierachain.config.settings import get_settings
from hierachain.security.verify_api_key import VerifyAPIKey

# Configure logging
logging.basicConfig(level=logging.INFO)
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

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    # Get settings
    settings = get_settings()
    api_config = settings.get_api_config()

    # Initialize implementation with settings
    if settings.AUTH_ENABLED:
        auth_dependency = VerifyAPIKey(settings.get_auth_config())
    else:
        # No-op dependency
        auth_dependency = lambda: None

    dependencies = [Depends(auth_dependency)] if settings.AUTH_ENABLED else []
    
    # Create FastAPI app
    fast_app = FastAPI(
        title="HieraChain Framework API",
        description="REST API for the HieraChain Framework - A general-purpose blockchain system for enterprise applications",
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

    # Add Security Headers Middleware
    @fast_app.middleware("http")
    async def security_headers_middleware(request, call_next):
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
        response.headers._list = [
            (name, value) for name, value in response.headers._list
            if name.lower() != b"server"
        ]
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
    
    # Root endpoint
    @fast_app.get("/")
    async def root():
        """Root endpoint with API information"""
        return {
            "name": "HieraChain Framework API",
            "version": api_config["version"],
            "description": "REST API for enterprise blockchain applications",
            "docs_url": "/docs",
            "health_check": "/api/v1/health",
            "features": [
                "Hierarchical chain structure (Main Chain + Sub-Chains)",
                "Event-based operations (no cryptocurrency terminology)",
                "Entity tracing across chains",
                "Proof submission mechanism",
                "Domain-specific implementations"
            ],
            "api_versions": [
                "/api/v1",
                "/api/v2" if 'v2_router' in locals() else None
            ]
        }
    
    # Global exception handler
    @fast_app.exception_handler(Exception)
    async def global_exception_handler(_request, exc):
        """Global exception handler"""
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
    
    # HTTP exception handler
    @fast_app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc):
        """HTTP exception handler"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP error",
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )
    

    # RecursionError handler (Prevent Deeply Nested JSON DoS)
    @fast_app.exception_handler(RecursionError)
    async def recursion_error_handler(_request, _exc):
        """Handle RecursionError usually caused by deeply nested JSON"""
        logger.warning("RecursionError detected - possible JSON bomb attempt")
        return JSONResponse(
            status_code=422,
            content={
                "error": "Unprocessable Entity",
                "message": "Input data too complex or deeply nested",
                "status_code": 422
            }
        )

    # Payload size limit middleware
    @fast_app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        max_upload_size = 5 * 1024 * 1024  # 5 MB
        if request.method == "POST":
            if "content-length" in request.headers:
                content_length = int(request.headers.get("content-length"))
                if content_length > max_upload_size:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Payload Too Large",
                            "message": f"Request body too large. Limit is {max_upload_size} bytes",
                            "status_code": 413
                        }
                    )
        return await call_next(request)

    # Simple In-Memory Rate Limiter Middleware
    _rate_limit_store = {}
    
    @fast_app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
            
        # Basic IP-based limiting
        client_ip = request.client.host if request.client else "unknown"
        current_time = int(time.time())
        window_size = 60  # 1 minute window
        rate_limit = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        
        # Clean up old entries occasionally (simple logic)
        if current_time % 60 == 0:
            keys_to_del = [k for k, v in _rate_limit_store.items() if v[0] < current_time - window_size]
            for k in keys_to_del:
                del _rate_limit_store[k]
        
        # Get user history
        if client_ip not in _rate_limit_store:
            _rate_limit_store[client_ip] = (current_time, 0)
            
        window_start, count = _rate_limit_store[client_ip]
        
        if current_time - window_start > window_size:
            # Reset window
            _rate_limit_store[client_ip] = (current_time, 1)
        else:
            if count >= rate_limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "message": "Rate limit exceeded. Please try again later.",
                        "status_code": 429
                    }
                )
            _rate_limit_store[client_ip] = (window_start, count + 1)
            
        return await call_next(request)

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