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
            config["dns_domain"] = domain  # Translate 'domain' → 'dns_domain' for internal use

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
        # Deploy Traefik via Ansible
        logger.info(f"Deploying Traefik via Ansible on {server_name}")

        # Build config
        config = {}
        if environment.get("ssl_email"):
            config["ssl_email"] = environment["ssl_email"]

        # Call orchestrator's dedicated Traefik deployment method
        result = await asyncio.to_thread(
            orchestrator.deploy_traefik,
            server_name=server_name,
            ssl_email=config.get("ssl_email")
        )

        # Update progress
        if result:
            job.update_progress(80, f"Traefik deployed successfully")

            # Update server state to add "traefik" to applications list
            server_data = orchestrator.get_server(server_name)
            if server_data:
                apps = server_data.get("applications", [])
                if "traefik" not in apps:
                    apps.append("traefik")
                    server_data["applications"] = apps
                    orchestrator.storage.state.update_server(server_name, server_data)
                    logger.info(f"Added 'traefik' to {server_name} applications list")
        else:
            job.update_progress(50, f"Traefik deployment failed")

        # Convert boolean result to dict format
        return {
            "success": result,
            "message": "Traefik deployed via Ansible" if result else "Traefik deployment failed",
            "app": app_name,
            "server": server_name,
            "deploy_method": "ansible"
        }

    elif app_name == "infrastructure":
        # Deploy infrastructure bundle (Traefik + Portainer) - v0.2.0
        logger.info(f"Deploying infrastructure bundle (Traefik + Portainer) on {server_name}")

        # Step 1: Deploy Traefik
        job.update_progress(20, "Deploying Traefik...")
        traefik_config = {}
        if environment.get("ssl_email"):
            traefik_config["ssl_email"] = environment["ssl_email"]

        traefik_result = await asyncio.to_thread(
            orchestrator.deploy_traefik,
            server_name=server_name,
            ssl_email=traefik_config.get("ssl_email")
        )

        if not traefik_result:
            logger.error(f"Traefik deployment failed for {server_name}")
            return {
                "success": False,
                "error": "Traefik deployment failed",
                "app": app_name,
                "server": server_name,
                "deploy_method": "ansible"
            }

        job.update_progress(50, "Traefik deployed, deploying Portainer...")

        # Step 2: Deploy Portainer
        portainer_config = {"environment": environment}
        if domain:
            portainer_config["dns_domain"] = domain

        portainer_result = await asyncio.to_thread(
            orchestrator.deploy_portainer,
            server_name=server_name,
            config=portainer_config
        )

        if not portainer_result:
            logger.error(f"Portainer deployment failed for {server_name}")
            return {
                "success": False,
                "error": "Portainer deployment failed (Traefik succeeded)",
                "app": app_name,
                "server": server_name,
                "deploy_method": "ansible"
            }

        job.update_progress(90, "Infrastructure bundle deployed successfully")

        # Update server state to add "infrastructure" to applications list
        # This is necessary for validation in app_deployer.py
        server_data = orchestrator.get_server(server_name)
        if server_data:
            apps = server_data.get("applications", [])
            if "infrastructure" not in apps:
                apps.append("infrastructure")
                server_data["applications"] = apps
                orchestrator.storage.state.update_server(server_name, server_data)
                logger.info(f"Added 'infrastructure' to {server_name} applications list")

        # Both deployed successfully
        return {
            "success": True,
            "message": "Infrastructure bundle deployed successfully (Traefik + Portainer)",
            "app": app_name,
            "server": server_name,
            "deploy_method": "ansible",
            "components_deployed": ["traefik", "portainer"]
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
