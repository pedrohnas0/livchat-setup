"""
Job Executors Registry

This module contains the registry of executor functions for different job types.
Executor functions are async functions that take (Job, Orchestrator) and execute the job.

Pattern:
    async def execute_my_job(job: Job, orchestrator: Orchestrator) -> Any:
        # Update progress
        job.update_progress(10, "Starting...")

        # Do the work
        result = await orchestrator.do_something(job.params)

        # Update progress
        job.update_progress(100, "Completed")

        return result

Registry:
    EXECUTOR_REGISTRY = {
        "my_job_type": execute_my_job,
        "other_job_type": execute_other_job,
    }
"""

from typing import Dict, Callable, Awaitable, Any

from .server_executors import (
    execute_create_server,
    execute_setup_server,
    execute_delete_server,
)
from .app_executors import (
    execute_deploy_app,
    execute_undeploy_app,
)
from .infrastructure_executors import (
    execute_deploy_infrastructure,
)

# Executor Registry - Maps job_type to executor function
EXECUTOR_REGISTRY: Dict[str, Callable[[Any, Any], Awaitable[Any]]] = {
    # Server operations
    "create_server": execute_create_server,
    "setup_server": execute_setup_server,
    "delete_server": execute_delete_server,

    # App operations
    "deploy_app": execute_deploy_app,
    "undeploy_app": execute_undeploy_app,

    # Infrastructure operations
    "deploy_infrastructure": execute_deploy_infrastructure,
}
