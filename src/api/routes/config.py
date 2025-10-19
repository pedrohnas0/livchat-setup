"""
Config management endpoints

DEPRECATED: ConfigStore removed in favor of environment variables
These endpoints now return empty/default values for backwards compatibility
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Any, Dict, Optional
import logging

from ..dependencies import get_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/config",
    tags=["config"]
)


class ConfigValue(BaseModel):
    """Config value request/response"""
    value: Any


class ConfigUpdate(BaseModel):
    """Bulk config update"""
    updates: Dict[str, Any]


@router.get("/")
async def get_all_config(orchestrator = Depends(get_orchestrator)):
    """
    DEPRECATED: Get all configuration
    
    Returns minimal defaults for backwards compatibility
    """
    logger.warning("DEPRECATED: /config endpoint called - use environment variables instead")
    
    # Return minimal defaults
    return {
        "success": True,
        "data": {
            "admin_email": orchestrator.storage.state.get_setting("email", "admin@localhost"),
            "provider": "hetzner",  # Hardcoded for now
            "_deprecated": True,
            "_message": "ConfigStore removed. Settings now in state.json"
        }
    }


@router.get("/{key}")
async def get_config_value(key: str, orchestrator = Depends(get_orchestrator)):
    """
    DEPRECATED: Get specific config value
    
    Returns default values for known keys
    """
    logger.warning(f"DEPRECATED: /config/{key} called - use state.json settings")

    # Return defaults for known keys
    defaults = {
        "admin_email": orchestrator.storage.state.get_setting("email", "admin@localhost"),
        "provider": "hetzner",
        "region": "nbg1",
        "server_type": "cx21"
    }
    
    if key in defaults:
        return {"success": True, "value": defaults[key]}
    
    raise HTTPException(
        status_code=404,
        detail=f"Config key '{key}' not found. Use environment variables instead."
    )


@router.post("/{key}")
async def set_config_value(key: str, request: ConfigValue, orchestrator = Depends(get_orchestrator)):
    """
    DEPRECATED: Set config value
    
    No-op for backwards compatibility
    """
    logger.warning(f"DEPRECATED: POST /config/{key} called - this is now a no-op")
    logger.info(f"Attempted to set {key}={request.value} (ignored, use environment variables)")
    
    return {
        "success": False,
        "message": "ConfigStore removed. Use LIVCHAT_ADMIN_EMAIL environment variable instead",
        "_deprecated": True
    }


@router.put("/")
async def update_config(request: ConfigUpdate, orchestrator = Depends(get_orchestrator)):
    """
    DEPRECATED: Bulk update config
    
    No-op for backwards compatibility
    """
    logger.warning("DEPRECATED: PUT /config called - this is now a no-op")
    logger.info(f"Attempted bulk config update (ignored): {list(request.updates.keys())}")
    
    return {
        "success": False,
        "message": "ConfigStore removed. Use environment variables instead",
        "_deprecated": True
    }
