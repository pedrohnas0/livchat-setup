"""
Server routes for LivChatSetup API

Endpoints for server management:
- POST /api/servers - Create server (async job)
- GET /api/servers - List servers
- GET /api/servers/{name} - Get server details
- DELETE /api/servers/{name} - Delete server (async job)
- POST /api/servers/{name}/setup - Setup server (async job)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import logging

try:
    from ..dependencies import get_job_manager, get_orchestrator
    from ..models.server import (
        ServerCreateRequest,
        ServerSetupRequest,
        ServerInfo,
        ServerListResponse,
        ServerCreateResponse,
        ServerDeleteResponse,
        ServerSetupResponse
    )
    from ...job_manager import JobManager
    from ...orchestrator import Orchestrator
except ImportError:
    from src.api.dependencies import get_job_manager, get_orchestrator
    from src.api.models.server import (
        ServerCreateRequest,
        ServerSetupRequest,
        ServerInfo,
        ServerListResponse,
        ServerCreateResponse,
        ServerDeleteResponse,
        ServerSetupResponse
    )
    from src.job_manager import JobManager
    from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/servers", tags=["Servers"])


def _server_data_to_info(name: str, data: dict) -> ServerInfo:
    """Convert server state data to ServerInfo model"""
    return ServerInfo(
        name=name,
        provider=data.get("provider", "unknown"),
        server_type=data.get("type", data.get("server_type", "unknown")),  # state uses "type"
        region=data.get("region", "unknown"),
        ip_address=data.get("ip", data.get("ip_address")),  # state uses "ip"
        status=data.get("status", "unknown"),
        created_at=data.get("created_at"),
        metadata=data.get("metadata", {})
    )


@router.post("", response_model=ServerCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_server(
    request: ServerCreateRequest,
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Create a new server (async operation)

    Creates a job for server creation and returns immediately.
    Use the job_id to track progress.

    Steps performed by the job:
    1. Create server on provider (Hetzner, DigitalOcean, etc.)
    2. Wait for server to be ready
    3. Add to state

    Returns:
        202 Accepted with job_id for tracking
    """
    try:
        # Create job for server creation
        job = job_manager.create_job(
            job_type="create_server",
            params={
                "name": request.name,
                "server_type": request.server_type,
                "region": request.region,
                "image": request.image,
                "ssh_keys": request.ssh_keys or []
            }
        )

        logger.info(f"Created job {job.job_id} for server creation: {request.name}")

        # TODO: Start background task to execute job
        # For now, job is created but not executed automatically
        # This will be implemented when we add background workers

        return ServerCreateResponse(
            job_id=job.job_id,
            message=f"Server creation started for {request.name}",
            server_name=request.name
        )

    except Exception as e:
        logger.error(f"Failed to create server job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ServerListResponse)
async def list_servers(
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    List all servers

    Returns servers from state (synchronous operation).
    Shows all servers that have been created and are tracked by the system.
    """
    try:
        # Get servers from state
        servers_dict = orchestrator.storage.state.list_servers()

        # Convert to ServerInfo models
        servers = [
            _server_data_to_info(name, data)
            for name, data in servers_dict.items()
        ]

        return ServerListResponse(
            servers=servers,
            total=len(servers)
        )

    except Exception as e:
        logger.error(f"Failed to list servers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}", response_model=ServerInfo)
async def get_server(
    name: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Get server details by name

    Returns complete server information from state.

    Raises:
        404: Server not found
    """
    server_data = orchestrator.storage.state.get_server(name)

    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server {name} not found"
        )

    return _server_data_to_info(name, server_data)


@router.delete("/{name}", response_model=ServerDeleteResponse, status_code=status.HTTP_202_ACCEPTED)
async def delete_server(
    name: str,
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Delete a server (async operation)

    Creates a job for server deletion and returns immediately.
    Use the job_id to track progress.

    Steps performed by the job:
    1. Delete server on provider
    2. Remove from state
    3. Cleanup DNS records (if configured)

    Raises:
        404: Server not found

    Returns:
        202 Accepted with job_id for tracking
    """
    # Check if server exists
    server_data = orchestrator.storage.state.get_server(name)
    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server {name} not found"
        )

    try:
        # Create job for server deletion
        job = job_manager.create_job(
            job_type="delete_server",
            params={
                "name": name,
                "provider_id": server_data.get("provider_id"),
                "provider": server_data.get("provider", "hetzner")
            }
        )

        logger.info(f"Created job {job.job_id} for server deletion: {name}")

        # TODO: Start background task to execute job

        return ServerDeleteResponse(
            job_id=job.job_id,
            message=f"Server deletion started for {name}",
            server_name=name
        )

    except Exception as e:
        logger.error(f"Failed to create delete job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/setup", response_model=ServerSetupResponse, status_code=status.HTTP_202_ACCEPTED)
async def setup_server(
    name: str,
    request: Optional[ServerSetupRequest] = None,
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Setup server with infrastructure (async operation)

    Creates a job for server setup and returns immediately.
    Use the job_id to track progress.

    Steps performed by the job:
    1. Update system packages
    2. Install Docker (if enabled)
    3. Initialize Docker Swarm (if enabled)
    4. Deploy Traefik reverse proxy (if enabled)
    5. Deploy Portainer (if enabled)

    Raises:
        404: Server not found

    Returns:
        202 Accepted with job_id for tracking
    """
    # Check if server exists
    server_data = orchestrator.storage.state.get_server(name)
    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server {name} not found"
        )

    # Use default setup if not provided
    if request is None:
        request = ServerSetupRequest()

    try:
        # Create job for server setup
        job = job_manager.create_job(
            job_type="setup_server",
            params={
                "server_name": name,  # Changed from "name" to match executor expectations
                "ssl_email": request.ssl_email if hasattr(request, 'ssl_email') else "admin@example.com",
                "network_name": request.network_name if hasattr(request, 'network_name') else "livchat_network",
                "timezone": request.timezone if hasattr(request, 'timezone') else "UTC"
            }
        )

        logger.info(f"Created job {job.job_id} for server setup: {name}")

        # TODO: Start background task to execute job

        return ServerSetupResponse(
            job_id=job.job_id,
            message=f"Server setup started for {name}",
            server_name=name
        )

    except Exception as e:
        logger.error(f"Failed to create setup job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
