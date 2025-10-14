"""
Server routes for LivChatSetup API

Endpoints for server management:
- POST /api/servers - Create server (async job)
- GET /api/servers - List servers
- GET /api/servers/{name} - Get server details
- DELETE /api/servers/{name} - Delete server (async job)
- POST /api/servers/{name}/setup - Setup server (async job)
- POST /api/servers/{name}/dns - Configure DNS for server
- GET /api/servers/{name}/dns - Get DNS configuration
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
        ServerSetupResponse,
        DNSConfigureRequest,
        DNSConfigureResponse,
        DNSGetResponse,
        DNSConfig
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
        ServerSetupResponse,
        DNSConfigureRequest,
        DNSConfigureResponse,
        DNSGetResponse,
        DNSConfig
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
        job = await job_manager.create_job(
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
    verify_provider: bool = True,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Get server details by name

    Returns complete server information from state.
    Optionally verifies the server still exists in the cloud provider.

    Args:
        name: Server name
        verify_provider: If True, checks if server exists in provider (default: True)

    Raises:
        404: Server not found (or deleted in provider)
    """
    server_data = orchestrator.storage.state.get_server(name)

    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server {name} not found"
        )

    # Double-check with provider if requested
    if verify_provider and server_data.get("provider") == "hetzner":
        server_id = server_data.get("id")

        if server_id:
            # Initialize provider if needed (lazy load from vault)
            if not orchestrator.provider:
                provider_name = orchestrator.storage.config.get("provider", "hetzner")
                token = orchestrator.storage.secrets.get_secret(f"{provider_name}_token")
                if token:
                    from src.providers.hetzner import HetznerProvider
                    orchestrator.provider = HetznerProvider(token)
                    logger.debug(f"Provider {provider_name} initialized for verification")

            # Only verify if provider was successfully initialized
            if orchestrator.provider:
                try:
                    # Try to get server from Hetzner
                    provider_server = orchestrator.provider.get_server(server_id)

                    # Update state with fresh data from provider
                    if provider_server:
                        server_data["status"] = provider_server.get("status", server_data.get("status"))
                        logger.debug(f"Server {name} verified with provider: {provider_server.get('status')}")

                except ValueError:
                    # Server not found in Hetzner - was deleted manually
                    logger.warning(f"Server {name} exists in state but not found in Hetzner (ID: {server_id})")

                    # Update state to reflect deletion
                    server_data["status"] = "deleted_externally"
                    orchestrator.storage.state.update_server(name, server_data)

                    raise HTTPException(
                        status_code=404,
                        detail=f"Server {name} was deleted externally (not found in provider)"
                    )
                except Exception as e:
                    error_msg = str(e).lower()

                    # Check if error indicates server was deleted (not found)
                    if "not found" in error_msg or "not_found" in error_msg:
                        logger.warning(f"Server {name} exists in state but not found in Hetzner (ID: {server_id})")

                        # Update state to reflect deletion
                        server_data["status"] = "deleted_externally"
                        orchestrator.storage.state.update_server(name, server_data)

                        raise HTTPException(
                            status_code=404,
                            detail=f"Server {name} was deleted externally (not found in provider)"
                        )

                    # Other provider errors (network, auth, etc) - use cached state
                    logger.error(f"Failed to verify server {name} with provider: {e}")
                    logger.warning(f"Returning cached state for {name} (provider check failed)")
            else:
                logger.warning(f"Provider not available for verification (no token in vault)")

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
        job = await job_manager.create_job(
            job_type="delete_server",
            params={
                "server_name": name,  # Changed from "name" to match executor expectations
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
    request: ServerSetupRequest,  # v0.2.0: Now REQUIRED (DNS mandatory)
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Setup server with infrastructure (async operation) - v0.2.0

    Creates a job for server setup and returns immediately.
    Use the job_id to track progress.

    v0.2.0 Changes:
    - DNS configuration (zone_name) is now REQUIRED
    - Traefik and Portainer are NO LONGER deployed during setup
    - They must be deployed separately as "base-infrastructure" app

    Steps performed by the job:
    1. Update system packages and configure timezone
    2. Install Docker
    3. Initialize Docker Swarm with overlay network
    4. Save DNS configuration to server state

    After setup, deploy base-infrastructure:
    POST /api/apps/deploy with app_name="base-infrastructure"

    Raises:
        404: Server not found
        400: Invalid DNS configuration

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

    # v0.2.0: Validate zone_name is provided
    if not request.zone_name:
        raise HTTPException(
            status_code=400,
            detail="zone_name is required for server setup (v0.2.0)"
        )

    try:
        # Create job for server setup with DNS configuration
        job = await job_manager.create_job(
            job_type="setup_server",
            params={
                "server_name": name,
                "zone_name": request.zone_name,  # v0.2.0: DNS required
                "subdomain": request.subdomain,  # v0.2.0: Optional subdomain
                "ssl_email": request.ssl_email,
                "network_name": request.network_name,
                "timezone": request.timezone
            }
        )

        logger.info(f"Created job {job.job_id} for server setup: {name} (DNS: {request.zone_name})")

        # TODO: Start background task to execute job

        return ServerSetupResponse(
            job_id=job.job_id,
            message=f"Server setup started for {name} with DNS {request.zone_name}",
            server_name=name
        )

    except Exception as e:
        logger.error(f"Failed to create setup job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{name}/dns", response_model=DNSConfigureResponse)
async def update_server_dns(
    name: str,
    request: DNSConfigureRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Update DNS configuration for a server (v0.2.0)

    Updates the DNS zone and optional subdomain for an existing server.
    Use this if you need to change the zone or subdomain after setup.

    NOTE: Changing DNS may require redeploying apps to update domains.

    Example:
    - zone_name: "livchat.ai"
    - subdomain: "lab"
    - Apps will use pattern: {app}.lab.livchat.ai

    Args:
        name: Server name
        request: DNS configuration (zone_name and optional subdomain)

    Returns:
        Success confirmation with DNS configuration

    Raises:
        404: Server not found
    """
    # Check if server exists
    server_data = orchestrator.storage.state.get_server(name)
    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server {name} not found"
        )

    try:
        # Prepare DNS config
        dns_config_dict = {
            "zone_name": request.zone_name
        }
        if request.subdomain:
            dns_config_dict["subdomain"] = request.subdomain

        # Update server with DNS config (v0.2.0: using dns_config, not dns_info)
        server_data["dns_config"] = dns_config_dict
        orchestrator.storage.state.update_server(name, server_data)

        logger.info(f"DNS updated for server {name}: {dns_config_dict}")

        # Build response
        dns_config = DNSConfig(**dns_config_dict)

        return DNSConfigureResponse(
            success=True,
            message=f"DNS configuration updated for server '{name}'. Apps may need redeployment to use new domains.",
            server_name=name,
            dns_config=dns_config
        )

    except Exception as e:
        logger.error(f"Failed to update DNS for {name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/dns", response_model=DNSConfigureResponse, deprecated=True)
async def configure_server_dns(
    name: str,
    request: DNSConfigureRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    [DEPRECATED v0.2.0] Configure DNS for a server

    ⚠️ DEPRECATED: Use PUT /{name}/dns instead.
    This endpoint is kept for backward compatibility but will be removed in v0.3.0.

    In v0.2.0, DNS is configured automatically during setup.
    Use this endpoint only if you need to update DNS after setup.

    Associates a DNS zone and optional subdomain with the server.
    This configuration is stored in the server's state and will be used
    automatically when deploying applications.

    Example:
    - zone_name: "livchat.ai"
    - subdomain: "lab"
    - Apps will use pattern: {app}.lab.livchat.ai

    Args:
        name: Server name
        request: DNS configuration (zone_name and optional subdomain)

    Returns:
        Success confirmation with DNS configuration

    Raises:
        404: Server not found
    """
    # Check if server exists
    server_data = orchestrator.storage.state.get_server(name)
    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server {name} not found"
        )

    try:
        # Prepare DNS config
        dns_config_dict = {
            "zone_name": request.zone_name
        }
        if request.subdomain:
            dns_config_dict["subdomain"] = request.subdomain

        # Update server with DNS config (v0.2.0: using dns_config for consistency)
        server_data["dns_config"] = dns_config_dict
        orchestrator.storage.state.update_server(name, server_data)

        logger.info(f"DNS configured for server {name}: {dns_config_dict}")

        # Build response
        dns_config = DNSConfig(**dns_config_dict)

        return DNSConfigureResponse(
            success=True,
            message=f"DNS configuration saved for server '{name}'",
            server_name=name,
            dns_config=dns_config
        )

    except Exception as e:
        logger.error(f"Failed to configure DNS for {name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/dns", response_model=DNSGetResponse)
async def get_server_dns(
    name: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Get DNS configuration for a server

    Returns the DNS zone and subdomain (if configured) for the server.

    Args:
        name: Server name

    Returns:
        DNS configuration

    Raises:
        404: Server not found or DNS not configured
    """
    # Check if server exists
    server_data = orchestrator.storage.state.get_server(name)
    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server {name} not found"
        )

    # Check if DNS is configured (v0.2.0: using dns_config)
    dns_config_dict = server_data.get("dns_config")
    if not dns_config_dict:
        raise HTTPException(
            status_code=404,
            detail=f"DNS not configured for server {name}"
        )

    try:
        dns_config = DNSConfig(**dns_config_dict)

        return DNSGetResponse(
            server_name=name,
            dns_config=dns_config
        )

    except Exception as e:
        logger.error(f"Failed to get DNS for {name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
