"""
FastAPI server for LivChatSetup

Main application with middleware, exception handlers, and route inclusion
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

try:
    from .routes import system, jobs, servers, config, apps, providers, secrets
    from .background import lifespan
except ImportError:
    from src.api.routes import system, jobs, servers, config, apps, providers, secrets
    from src.api.background import lifespan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application with lifespan
app = FastAPI(
    title="LivChatSetup API",
    description="Automated infrastructure orchestration for LivChat",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan  # Added lifespan for background job processing
)

# CORS middleware - Allow all origins for development
# TODO: Configure properly for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(system.router, tags=["System"])
app.include_router(jobs.router)
app.include_router(servers.router)
app.include_router(config.router)
app.include_router(secrets.router)
app.include_router(apps.router)
app.include_router(providers.router)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled exceptions

    Logs the error and returns a standardized JSON response
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": str(exc) if app.debug else None
        }
    )

# Note: Startup/shutdown logic moved to lifespan context manager in background.py
# This provides better control over async resource management
