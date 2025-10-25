"""
State routes for LivChatSetup API

Endpoints for state.json management with dot notation:
- GET /api/state - Get value at path or entire state
- PUT /api/state - Set value at path
- DELETE /api/state - Delete key at path
- GET /api/state/keys - List keys at path
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
import logging

try:
    from ..dependencies import get_orchestrator
    from ..models.state import (
        StateGetRequest,
        StateSetRequest,
        StateDeleteRequest,
        StateListRequest,
        StateResponse,
        StateAction
    )
    from ...orchestrator import Orchestrator
except ImportError:
    from api.dependencies import get_orchestrator
    from api.models.state import (
        StateGetRequest,
        StateSetRequest,
        StateDeleteRequest,
        StateListRequest,
        StateResponse,
        StateAction
    )
    from orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/state", tags=["State"])


@router.get("", response_model=StateResponse)
async def get_state(
    path: Optional[str] = Query(
        None,
        description="Dot notation path (e.g., 'servers.prod.ip'). None returns entire state",
        examples=["servers.prod.ip", "settings.admin_email", "servers"]
    ),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Get value from state at specified path

    Uses dot notation to access nested values in state.json.

    Args:
        path: Dot notation path (optional). If None, returns entire state.

    Returns:
        StateResponse with value at path

    Raises:
        404: Path not found in state

    Examples:
        - GET /api/state?path=servers.prod.ip -> {"success": true, "value": "1.2.3.4"}
        - GET /api/state?path=servers -> {"success": true, "value": {...all servers...}}
        - GET /api/state -> {"success": true, "value": {...entire state...}}
    """
    try:
        # Get value at path (or entire state if no path)
        if path:
            value = orchestrator.storage.state.get_by_path(path)
        else:
            # No path - return entire state (private _state attribute)
            value = orchestrator.storage.state._state

        return StateResponse(
            success=True,
            action=StateAction.GET,
            path=path,
            value=value,
            message=f"Retrieved value at path: {path}" if path else "Retrieved entire state"
        )

    except KeyError as e:
        logger.warning(f"Path not found: {path} - {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Path not found in state: {path}"
        )
    except Exception as e:
        logger.error(f"Failed to get state at path '{path}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("", response_model=StateResponse)
async def set_state(
    request: StateSetRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Set value in state at specified path

    Creates intermediate dictionaries if they don't exist.
    Automatically saves to state.json.

    Args:
        request: StateSetRequest with path and value

    Returns:
        StateResponse confirming set operation

    Examples:
        - PUT /api/state {"path": "servers.prod.ip", "value": "1.2.3.4"}
        - PUT /api/state {"path": "servers.new.ip", "value": "10.0.0.1"} # Creates 'new' dict
        - PUT /api/state {"path": "servers.prod.dns_config", "value": {"zone_name": "example.com"}}
    """
    try:
        # Set value at path
        orchestrator.storage.state.set_by_path(request.path, request.value)

        return StateResponse(
            success=True,
            action=StateAction.SET,
            path=request.path,
            value=request.value,
            message=f"Set value at path: {request.path}"
        )

    except Exception as e:
        logger.error(f"Failed to set state at path '{request.path}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("", response_model=StateResponse)
async def delete_state(
    path: str = Query(
        ...,
        description="Dot notation path of key to delete",
        examples=["servers.prod.status", "settings.admin_email"]
    ),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Delete key from state at specified path

    Removes the key at the specified path and saves to state.json.

    Args:
        path: Dot notation path to delete

    Returns:
        StateResponse confirming deletion

    Raises:
        404: Path not found in state

    Examples:
        - DELETE /api/state?path=servers.prod.status
        - DELETE /api/state?path=servers.prod.dns_config.subdomain
    """
    try:
        # Delete key at path
        orchestrator.storage.state.delete_by_path(path)

        return StateResponse(
            success=True,
            action=StateAction.DELETE,
            path=path,
            message=f"Deleted key at path: {path}"
        )

    except KeyError as e:
        logger.warning(f"Path not found for deletion: {path} - {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Path not found in state: {path}"
        )
    except Exception as e:
        logger.error(f"Failed to delete state at path '{path}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/keys", response_model=StateResponse)
async def list_keys(
    path: Optional[str] = Query(
        None,
        description="Dot notation path to list keys from. None lists root keys",
        examples=["servers", "servers.prod", "settings"]
    ),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    List keys at specified path

    Returns list of keys if path points to a dict, empty list otherwise.

    Args:
        path: Dot notation path (optional). None lists root keys.

    Returns:
        StateResponse with list of keys

    Raises:
        404: Path not found in state

    Examples:
        - GET /api/state/keys -> ["servers", "settings", "deployments", "jobs"]
        - GET /api/state/keys?path=servers -> ["prod", "dev", "staging"]
        - GET /api/state/keys?path=servers.prod -> ["ip", "dns_config", "status"]
        - GET /api/state/keys?path=servers.prod.ip -> [] (not a dict)
    """
    try:
        # List keys at path
        keys = orchestrator.storage.state.list_keys_at_path(path)

        return StateResponse(
            success=True,
            action=StateAction.LIST,
            path=path,
            keys=keys,
            message=f"Listed {len(keys)} keys at path: {path}" if path else f"Listed {len(keys)} root keys"
        )

    except KeyError as e:
        logger.warning(f"Path not found for listing: {path} - {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Path not found in state: {path}"
        )
    except Exception as e:
        logger.error(f"Failed to list keys at path '{path}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
