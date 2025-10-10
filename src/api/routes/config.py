"""
Configuration routes for LivChatSetup API

Endpoints for configuration management (synchronous):
- GET /api/config - Get all configuration
- GET /api/config/{key} - Get specific config value
- PUT /api/config/{key} - Set config value
- POST /api/config - Update multiple values
"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging

try:
    from ..dependencies import get_orchestrator
    from ..models.config import (
        ConfigGetResponse,
        ConfigSetRequest,
        ConfigSetResponse,
        ConfigAllResponse,
        ConfigUpdateRequest,
        ConfigUpdateResponse
    )
    from ...orchestrator import Orchestrator
except ImportError:
    from src.api.dependencies import get_orchestrator
    from src.api.models.config import (
        ConfigGetResponse,
        ConfigSetRequest,
        ConfigSetResponse,
        ConfigAllResponse,
        ConfigUpdateRequest,
        ConfigUpdateResponse
    )
    from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("", response_model=ConfigAllResponse)
async def get_all_config(
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Get all configuration

    Returns the complete configuration dictionary.
    Configuration is stored in ~/.livchat/config.yaml
    """
    try:
        config = orchestrator.storage.config.load()

        return ConfigAllResponse(config=config)

    except Exception as e:
        logger.error(f"Failed to get configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}", response_model=ConfigGetResponse)
async def get_config_value(
    key: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Get specific configuration value

    Supports dot notation for nested keys (e.g., "providers.hetzner.region")

    Raises:
        404: Key not found
    """
    try:
        value = orchestrator.storage.config.get(key)

        if value is None:
            raise HTTPException(
                status_code=404,
                detail=f"Configuration key '{key}' not found"
            )

        return ConfigGetResponse(key=key, value=value)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config key {key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{key}", response_model=ConfigSetResponse)
async def set_config_value(
    key: str,
    request: ConfigSetRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Set configuration value

    Updates or creates a configuration value.
    Supports dot notation for nested keys (e.g., "providers.hetzner.token")

    Configuration is automatically saved to ~/.livchat/config.yaml
    """
    try:
        orchestrator.storage.config.set(key, request.value)

        logger.info(f"Configuration key '{key}' set to: {request.value}")

        return ConfigSetResponse(
            success=True,
            message=f"Configuration key '{key}' updated successfully",
            key=key,
            value=request.value
        )

    except Exception as e:
        logger.error(f"Failed to set config key {key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ConfigUpdateResponse)
async def update_config(
    request: ConfigUpdateRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Update multiple configuration values

    Performs a bulk update of configuration values.
    All updates are applied in a single save operation.

    Returns count of updated keys and list of keys that were updated.
    """
    try:
        updates = request.updates
        updated_keys = list(updates.keys())
        updated_count = len(updated_keys)

        if updated_count == 0:
            return ConfigUpdateResponse(
                success=True,
                message="No updates provided",
                updated_count=0,
                updated_keys=[]
            )

        # Update all keys
        orchestrator.storage.config.update(updates)

        logger.info(f"Updated {updated_count} configuration keys: {updated_keys}")

        return ConfigUpdateResponse(
            success=True,
            message=f"Updated {updated_count} configuration values",
            updated_count=updated_count,
            updated_keys=updated_keys
        )

    except Exception as e:
        logger.error(f"Failed to update configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
