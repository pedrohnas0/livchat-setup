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

    # Route to appropriate deployment method
    # Infrastructure apps have dedicated deployment methods in orchestrator

    if app_name == "portainer":
        # Step 1/2: Starting deployment
        job.advance_step(1, 2, f"Deploying Portainer to {server_name}")
        # Deploy Portainer via Ansible
        logger.info(f"Deploying Portainer via Ansible on {server_name}")

        # Get server to access dns_config
        server_data = orchestrator.get_server(server_name)
        if not server_data:
            return {
                "success": False,
                "error": f"Server {server_name} not found",
                "app": app_name,
                "server": server_name
            }

        # Build config
        config = {
            "environment": environment,
        }

        # Auto-build domain from server's dns_config if not explicitly provided
        if domain:
            config["dns_domain"] = domain  # Use explicit domain if provided
        else:
            # Build domain from server's dns_config (v0.2.0)
            dns_config = server_data.get("dns_config", {})
            zone_name = dns_config.get("zone_name")
            subdomain = dns_config.get("subdomain")

            if zone_name:
                # Use Portainer's dns_prefix (ptn) from app definition
                dns_prefix = "ptn"
                if subdomain:
                    auto_domain = f"{dns_prefix}.{subdomain}.{zone_name}"
                else:
                    auto_domain = f"{dns_prefix}.{zone_name}"

                config["dns_domain"] = auto_domain
                logger.info(f"Auto-built Portainer domain from dns_config: {auto_domain}")

        # Call orchestrator's dedicated Portainer deployment method
        # This method is SYNCHRONOUS but we're in an ASYNC context
        # Use asyncio.to_thread() to run it in a separate thread
        result = await asyncio.to_thread(
            orchestrator.deploy_portainer,
            server_name=server_name,
            config=config
        )

        # Step 2/2: Deployment complete
        if result:
            job.advance_step(2, 2, "Portainer deployed successfully")
        else:
            job.advance_step(2, 2, "Portainer deployment failed")

        job.update_progress(100, "Portainer deployment completed")

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

        # Step 1/2: Starting deployment
        job.advance_step(1, 2, f"Deploying Traefik to {server_name}")

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

        # Step 2/2: Deployment complete
        if result:
            job.advance_step(2, 2, "Traefik deployed successfully")

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
            job.advance_step(2, 2, "Traefik deployment failed")

        job.update_progress(100, "Traefik deployment completed")

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

        # Step 1/3: Deploy Traefik
        job.advance_step(1, 3, "Deploying Traefik")
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
            job.advance_step(3, 3, "Infrastructure deployment failed")
            job.update_progress(100, "Infrastructure deployment failed")
            return {
                "success": False,
                "error": "Traefik deployment failed",
                "app": app_name,
                "server": server_name,
                "deploy_method": "ansible"
            }

        # Step 2/3: Deploy Portainer
        job.advance_step(2, 3, "Traefik deployed, deploying Portainer")
        # Get server to access dns_config
        server_data = orchestrator.get_server(server_name)
        if not server_data:
            return {
                "success": False,
                "error": f"Server {server_name} not found",
                "app": app_name,
                "server": server_name
            }

        portainer_config = {"environment": environment}

        # Auto-build domain from server's dns_config if not explicitly provided
        if domain:
            portainer_config["dns_domain"] = domain
        else:
            # Build domain from server's dns_config (v0.2.0)
            dns_config = server_data.get("dns_config", {})
            zone_name = dns_config.get("zone_name")
            subdomain = dns_config.get("subdomain")

            if zone_name:
                # Use Portainer's dns_prefix (ptn) from app definition
                dns_prefix = "ptn"
                if subdomain:
                    auto_domain = f"{dns_prefix}.{subdomain}.{zone_name}"
                else:
                    auto_domain = f"{dns_prefix}.{zone_name}"

                portainer_config["dns_domain"] = auto_domain
                logger.info(f"Auto-built Portainer domain from dns_config: {auto_domain}")

        portainer_result = await asyncio.to_thread(
            orchestrator.deploy_portainer,
            server_name=server_name,
            config=portainer_config
        )

        if not portainer_result:
            logger.error(f"Portainer deployment failed for {server_name}")
            job.advance_step(3, 3, "Infrastructure deployment failed")
            job.update_progress(100, "Infrastructure deployment failed")
            return {
                "success": False,
                "error": "Portainer deployment failed (Traefik succeeded)",
                "app": app_name,
                "server": server_name,
                "deploy_method": "ansible"
            }

        # Step 3/3: Deployment complete
        job.advance_step(3, 3, "Infrastructure bundle deployed successfully")

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

        # Final progress
        job.update_progress(100, "Infrastructure deployment completed")

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
