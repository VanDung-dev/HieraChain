"""
FastAPI server for Hierarchical Blockchain Framework

This module implements the REST API server for the Hierarchical Blockchain Framework.
The framework implements a hierarchical structure where the Main Chain only stores 
proofs from Sub-Chains.

The server uses FastAPI for high performance and includes proper error handling,
CORS support, and comprehensive logging.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
from contextlib import asynccontextmanager

from hierarchical_blockchain.api.v1.endpoints import router as v1_router
from hierarchical_blockchain.api.v2.endpoints import router as v2_router
from hierarchical_blockchain.config.settings import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Hierarchical Blockchain API server...")
    yield
    # Shutdown
    logger.info("Shutting down Hierarchical Blockchain API server...")

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    # Get settings
    settings = Settings()
    api_config = settings.get_api_config()
    
    # Create FastAPI app
    fast_app = FastAPI(
        title="Hierarchical Blockchain Framework API",
        description="REST API for the Hierarchical Blockchain Framework - A general-purpose blockchain system for enterprise applications",
        version=api_config["version"],
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    fast_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify allowed origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Try to include v1 router
    try:
        fast_app.include_router(v1_router)
        logger.info("API v1 router included successfully")
    except ImportError:
        logger.warning("API v1 router not available")
    
    # Try to include v2 router
    try:
        fast_app.include_router(v2_router)
        logger.info("API v2 router included successfully")
    except ImportError:
        logger.warning("API v2 router not available")
    
    # Root endpoint
    @fast_app.get("/")
    async def root():
        """Root endpoint with API information"""
        return {
            "name": "Hierarchical Blockchain Framework API",
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
    
    return fast_app

# Create app instance
app = create_app()

def run_server():
    """Run the server with uvicorn"""
    settings = Settings()
    api_config = settings.get_api_config()
    is_debug = settings.LOG_LEVEL == "DEBUG"
    
    uvicorn.run(
        "hierarchical_blockchain.api.server:app",
        host=api_config["host"],
        port=api_config["port"],
        reload=is_debug,
        log_level="info" if not is_debug else "debug"
    )

if __name__ == "__main__":
    run_server()