"""
Server Executor Functions

Executor functions for server-related jobs:
- create_server: Create new VPS server
- setup_server: Setup infrastructure on server
- delete_server: Delete/destroy server

Each executor takes (Job, Orchestrator) and updates job progress.
"""

import asyncio
import logging
from typing import Any, Dict
import functools

from src.job_manager import Job
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


async def execute_create_server(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute server creation job

    Args:
        job: Job instance with params (name, server_type, location, image)
        orchestrator: Orchestrator instance

    Returns:
        Server creation result with id, ip, status
    """
    logger.info(f"Executing create_server job {job.job_id}")

    # Extract params
    params = job.params
    name = params.get("name")
    server_type = params.get("server_type")
    region = params.get("location") or params.get("region")  # Support both for compatibility
    image = params.get("image", "debian-12")

    # Step 1: Creating server
    job.advance_step(1, 2, f"Creating server {name} on provider")

    # Create server via orchestrator
    # NOTE: create_server is SYNC (may take 30-60s)
    # Run in executor to avoid blocking event loop
    loop = asyncio.get_event_loop()
    create_func = functools.partial(
        orchestrator.create_server,
        name=name,
        server_type=server_type,
        region=region,
        image=image
    )
    result = await loop.run_in_executor(None, create_func)

    # Step 2: Server ready
    job.advance_step(2, 2, f"Server ready: {result.get('ip')}")
    job.update_progress(100, "Server creation completed")

    logger.info(f"Server {name} created successfully: {result.get('id')}")

    return result


async def execute_setup_server(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute server setup job with step-based progress tracking (v0.2.0: DNS required)

    Setup process has 4 main steps (v0.2.0 - simplified):
    1. Starting setup
    2. Base system setup (apt update, timezone, etc)
    3. Installing Docker and initializing Swarm
    4. Finalizing setup

    v0.2.0 Changes:
    - zone_name is now REQUIRED (not optional)
    - Traefik and Portainer are NO LONGER deployed during setup
    - They must be deployed separately as "infrastructure" app

    Args:
        job: Job instance with params (server_name, zone_name, subdomain, ssl_email, etc)
        orchestrator: Orchestrator instance

    Returns:
        Setup result with DNS configuration

    Note: The actual setup runs as a blocking Ansible execution. Future improvement
    would be to add progress callbacks from server_setup.full_setup() to report
    each step in real-time. For now, we show step 1/4 during execution and jump
    to 4/4 on completion. Time-based progress increment provides smooth updates.
    """
    logger.info(f"Executing setup_server job {job.job_id}")

    # Extract params
    params = job.params
    server_name = params.get("server_name")

    # v0.2.0: DNS configuration (zone_name required, subdomain optional)
    zone_name = params.get("zone_name")
    subdomain = params.get("subdomain")

    # Infrastructure configuration
    ssl_email = params.get("ssl_email", "admin@example.com")
    network_name = params.get("network_name", "livchat_network")
    timezone = params.get("timezone", "America/Sao_Paulo")

    # Validate required params (v0.2.0)
    if not zone_name:
        raise ValueError("zone_name is required for server setup (v0.2.0)")

    # Step 1: Starting setup (shows Etapa 1/4)
    dns_info = f" with DNS {zone_name}" + (f"/{subdomain}" if subdomain else "")
    job.advance_step(1, 4, f"Starting setup for {server_name}{dns_info}")

    # Setup server via orchestrator
    # NOTE: setup_server is SYNC (runs Ansible for 3-5min in v0.2.0)
    # Must run in executor to avoid blocking event loop
    # During this execution, time-based progress will slowly increment
    loop = asyncio.get_event_loop()
    setup_func = functools.partial(
        orchestrator.setup_server,
        server_name=server_name,
        zone_name=zone_name,  # v0.2.0: Required parameter
        subdomain=subdomain,  # v0.2.0: Optional parameter
        config={
            "ssl_email": ssl_email,
            "network_name": network_name,
            "timezone": timezone
        }
    )
    result = await loop.run_in_executor(None, setup_func)

    # Step 4: Setup complete (jumps to final step)
    job.advance_step(4, 4, "Finalizing server setup")
    job.update_progress(100, "Server setup completed successfully")

    logger.info(f"Server {server_name} setup completed successfully with DNS {zone_name}")

    return result


async def execute_delete_server(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute server deletion job

    Args:
        job: Job instance with params (server_name)
        orchestrator: Orchestrator instance

    Returns:
        Deletion result
    """
    logger.info(f"Executing delete_server job {job.job_id}")

    # Extract params
    params = job.params
    server_name = params.get("server_name")

    # Step 1: Deleting server (only step)
    job.advance_step(1, 1, f"Deleting server {server_name}")

    # Delete server via orchestrator
    # NOTE: delete_server is SYNC and returns bool (not Dict like others)
    # Run in executor to avoid blocking event loop
    loop = asyncio.get_event_loop()
    delete_func = functools.partial(
        orchestrator.delete_server,
        name=server_name
    )
    success = await loop.run_in_executor(None, delete_func)

    # Convert bool to Dict[str, Any] for consistency with other executors
    result = {
        "success": success,
        "server": server_name,
        "message": f"Server {server_name} {'deleted successfully' if success else 'deletion failed'}"
    }

    # Mark complete
    job.update_progress(100, "Server deletion completed")

    logger.info(f"Server {server_name} deleted: {success}")

    return result
