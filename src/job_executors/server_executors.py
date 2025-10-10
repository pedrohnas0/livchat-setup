"""
Server Executor Functions

Executor functions for server-related jobs:
- create_server: Create new VPS server
- setup_server: Setup infrastructure on server
- delete_server: Delete/destroy server

Each executor takes (Job, Orchestrator) and updates job progress.
"""

import logging
from typing import Any, Dict

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

    # Update progress
    job.update_progress(10, f"Creating server {name}...")

    # Create server via orchestrator
    result = orchestrator.create_server(  # NOTE: NOT async!
        name=name,
        server_type=server_type,
        region=region,
        image=image
    )

    # Update progress
    job.update_progress(80, f"Server created: {result.get('ip')}")

    # Wait for server to be ready
    job.update_progress(90, "Waiting for server to initialize...")

    # Final progress
    job.update_progress(100, "Server creation completed")

    logger.info(f"Server {name} created successfully: {result.get('id')}")

    return result


async def execute_setup_server(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute server setup job

    Args:
        job: Job instance with params (server_name, ssl_email, network_name, etc)
        orchestrator: Orchestrator instance

    Returns:
        Setup result with services installed
    """
    logger.info(f"Executing setup_server job {job.job_id}")

    # Extract params
    params = job.params
    server_name = params.get("server_name")
    ssl_email = params.get("ssl_email", "admin@example.com")
    network_name = params.get("network_name", "livchat_network")
    timezone = params.get("timezone", "UTC")

    # Update progress
    job.update_progress(10, f"Starting setup for {server_name}...")

    # Setup server via orchestrator
    # NOTE: setup_server is NOT async! Pass all config in dict
    result = orchestrator.setup_server(
        server_name=server_name,
        config={
            "ssl_email": ssl_email,
            "network_name": network_name,
            "timezone": timezone
        }
    )

    # Update progress
    job.update_progress(90, "Infrastructure setup completed")

    # Final progress
    job.update_progress(100, "Server setup completed")

    logger.info(f"Server {server_name} setup completed successfully")

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

    # Update progress
    job.update_progress(10, f"Deleting server {server_name}...")

    # Delete server via orchestrator
    # NOTE: delete_server expects 'name' parameter, NOT 'server_name'
    result = await orchestrator.delete_server(name=server_name)

    # Update progress
    job.update_progress(80, "Server deleted from provider")

    # Final progress
    job.update_progress(100, "Server deletion completed")

    logger.info(f"Server {server_name} deleted successfully")

    return result
