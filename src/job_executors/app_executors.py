"""
App Executor Functions

Executor functions for app-related jobs:
- deploy_app: Deploy application to server
- undeploy_app: Remove application from server

Each executor takes (Job, Orchestrator) and updates job progress.
"""

import logging
from typing import Any, Dict

from src.job_manager import Job
from src.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


async def execute_deploy_app(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute app deployment job with step-based progress

    Deployment steps:
    1. Resolving dependencies
    2. Deploying app
    3. Deployment complete

    Args:
        job: Job instance with params (app_name, server_name, environment, etc)
        orchestrator: Orchestrator instance

    Returns:
        Deployment result with app status
    """
    logger.info(f"Executing deploy_app job {job.job_id}")

    # Extract params
    params = job.params
    app_name = params.get("app_name")
    server_name = params.get("server_name")
    environment = params.get("environment", {})
    domain = params.get("domain")

    # Step 1: Resolving dependencies
    job.advance_step(1, 3, f"Resolving dependencies for {app_name}")

    # Step 2: Deploying app
    job.advance_step(2, 3, f"Deploying {app_name} to {server_name}")

    # Deploy app via orchestrator
    # NOTE: Pass environment and domain inside config dict
    config = {
        "environment": environment,
    }
    if domain:
        config["domain"] = domain  # Pass domain directly for template substitution

    result = await orchestrator.deploy_app(
        server_name=server_name,
        app_name=app_name,
        config=config
    )

    # Step 3: Deployment complete
    job.advance_step(3, 3, f"{app_name} deployed successfully")
    job.update_progress(100, "App deployment completed")

    logger.info(f"App {app_name} deployed successfully to {server_name}")

    return result


async def execute_undeploy_app(job: Job, orchestrator: Orchestrator) -> Dict[str, Any]:
    """
    Execute app undeployment job with step-based progress

    Undeployment steps:
    1. Removing app
    2. Undeployment complete

    Args:
        job: Job instance with params (app_name, server_name)
        orchestrator: Orchestrator instance

    Returns:
        Undeployment result
    """
    logger.info(f"Executing undeploy_app job {job.job_id}")

    # Extract params
    params = job.params
    app_name = params.get("app_name")
    server_name = params.get("server_name")

    # Step 1: Removing app
    job.advance_step(1, 2, f"Removing {app_name} from {server_name}")

    # Undeploy app via orchestrator
    result = await orchestrator.undeploy_app(
        app_name=app_name,
        server_name=server_name
    )

    # Step 2: Undeployment complete
    job.advance_step(2, 2, f"{app_name} removed successfully")
    job.update_progress(100, "App undeployment completed")

    logger.info(f"App {app_name} undeployed successfully from {server_name}")

    return result
