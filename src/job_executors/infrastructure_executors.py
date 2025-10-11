"""
Infrastructure Executor Functions

Executor functions for infrastructure-related jobs:
- deploy_infrastructure: Deploy infrastructure apps via Ansible (Portainer, Traefik)

Infrastructure apps use deploy_method: ansible and are deployed via Ansible playbooks
rather than via Portainer API.
"""

import asyncio
import logging
from typing import Any, Dict

from src.job_manager import Job
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


async def execute_deploy_infrastructure(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute infrastructure deployment job

    Infrastructure apps (Portainer, Traefik) are deployed via Ansible playbooks
    rather than via Portainer API. This executor routes to the appropriate
    deployment method based on app_name.

    Args:
        job: Job instance with params (app_name, server_name, environment, etc)
        orchestrator: Orchestrator instance

    Returns:
        Deployment result with infrastructure status
    """
    logger.info(f"Executing deploy_infrastructure job {job.job_id}")

    # Extract params
    params = job.params
    app_name = params.get("app_name")
    server_name = params.get("server_name")
    environment = params.get("environment", {})
    domain = params.get("domain")

    # Update progress
    job.update_progress(10, f"Deploying infrastructure: {app_name} to {server_name}...")

    # Route to appropriate deployment method
    # Infrastructure apps have dedicated deployment methods in orchestrator

    if app_name == "portainer":
        # Deploy Portainer via Ansible
        logger.info(f"Deploying Portainer via Ansible on {server_name}")

        # Build config
        config = {
            "environment": environment,
        }
        if domain:
            config["domain"] = domain

        # Call orchestrator's dedicated Portainer deployment method
        # This method is SYNCHRONOUS but we're in an ASYNC context
        # Use asyncio.to_thread() to run it in a separate thread
        result = await asyncio.to_thread(
            orchestrator.deploy_portainer,
            server_name=server_name,
            config=config
        )

        # Update progress
        if result:
            job.update_progress(80, f"Portainer deployed successfully")
        else:
            job.update_progress(50, f"Portainer deployment failed")

        # Convert boolean result to dict format
        return {
            "success": result,
            "message": "Portainer deployed via Ansible" if result else "Portainer deployment failed",
            "app": app_name,
            "server": server_name,
            "deploy_method": "ansible"
        }

    elif app_name == "traefik":
        # Traefik is deployed during server setup, not as standalone app
        logger.warning(f"Traefik deployment via API not yet supported (deployed during server setup)")

        return {
            "success": False,
            "error": "Traefik is deployed automatically during server setup",
            "app": app_name,
            "server": server_name
        }

    else:
        # Unknown infrastructure app
        logger.error(f"Unknown infrastructure app: {app_name}")

        return {
            "success": False,
            "error": f"Unknown infrastructure app: {app_name}",
            "app": app_name,
            "server": server_name
        }

    # Final progress
    job.update_progress(100, "Infrastructure deployment completed")
