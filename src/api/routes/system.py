"""
System routes for LivChatSetup API

Endpoints:
- GET /         - Welcome message + API info
- GET /health   - Health check
- POST /api/init - Initialize system
"""

from fastapi import APIRouter, Depends
from datetime import datetime
import logging

try:
    from ..dependencies import get_orchestrator
    from ..models.common import SuccessResponse, MessageResponse
    from ...orchestrator import Orchestrator
except ImportError:
    from src.api.dependencies import get_orchestrator
    from src.api.models.common import SuccessResponse, MessageResponse
    from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("/", response_model=dict)
async def root():
    """
    Welcome endpoint with API information

    Returns basic API info and links to documentation
    """
    return {
        "message": "Welcome to LivChatSetup API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@router.get("/health", response_model=dict)
async def health_check():
    """
    Health check endpoint

    Returns 200 OK if API is running
    Used by monitoring systems and load balancers
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/api/init", response_model=SuccessResponse)
async def initialize_system(
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Initialize LivChatSetup system

    Creates ~/.livchat directory with initial configuration.
    Safe to call multiple times (idempotent).

    Returns:
        SuccessResponse with config directory path
    """
    try:
        # Orchestrator is already initialized in get_orchestrator()
        # But we call init() again to ensure everything is set up
        # init() is idempotent
        orchestrator.init()

        logger.info("System initialized successfully")

        return SuccessResponse(
            success=True,
            message="LivChatSetup initialized successfully",
            data={
                "config_dir": str(orchestrator.config_dir)
            }
        )

    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        # Let FastAPI handle the exception and return 500
        raise
