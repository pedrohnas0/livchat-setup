"""
Application routes for LivChatSetup API

Endpoints for application management:
- GET /api/apps - List available apps
- GET /api/apps/{name} - Get app details
- POST /api/apps/{name}/deploy - Deploy app (async job)
- POST /api/apps/{name}/undeploy - Undeploy app (async job)
- GET /api/servers/{server_name}/apps - List deployed apps
"""

from fastapi import APIRouter, Depends, HTTPException, status
import logging

try:
    from ..dependencies import get_job_manager, get_orchestrator
    from ..models.app import (
        AppDeployRequest,
        AppDeployResponse,
        AppUndeployResponse,
        AppInfo,
        AppListResponse,
        DeployedAppInfo,
        DeployedAppListResponse
    )
    from ...job_manager import JobManager
    from ...orchestrator import Orchestrator
    from ...app_registry import AppRegistry
except ImportError:
    from src.api.dependencies import get_job_manager, get_orchestrator
    from src.api.models.app import (
        AppDeployRequest,
        AppDeployResponse,
        AppUndeployResponse,
        AppInfo,
        AppListResponse,
        DeployedAppInfo,
        DeployedAppListResponse
    )
    from src.job_manager import JobManager
    from src.orchestrator import Orchestrator
    from src.app_registry import AppRegistry

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["Applications"])


def get_app_registry() -> AppRegistry:
    """
    Get AppRegistry instance with loaded definitions

    This is a separate function to allow mocking in tests
    """
    from pathlib import Path

    registry = AppRegistry()

    # Load app definitions from standard location
    apps_dir = Path(__file__).parent.parent.parent.parent / "apps" / "definitions"
    if apps_dir.exists():
        registry.load_definitions(str(apps_dir))

    return registry


@router.get("/apps", response_model=AppListResponse)
async def list_apps():
    """
    List all available applications

    Returns the catalog of available applications that can be deployed.
    Applications are defined in apps/definitions/ directory.
    """
    try:
        registry = get_app_registry()
        apps = registry.list_apps()

        # Convert to AppInfo models
        app_infos = [
            AppInfo(
                name=app.get("name"),
                version=app.get("version"),
                description=app.get("description"),
                category=app.get("category"),
                dependencies=app.get("dependencies", []),
                deploy_method=app.get("deploy_method", "portainer")
            )
            for app in apps
        ]

        return AppListResponse(
            apps=app_infos,
            total=len(app_infos)
        )

    except Exception as e:
        logger.error(f"Failed to list apps: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apps/{name}", response_model=AppInfo)
async def get_app(name: str):
    """
    Get application details

    Returns complete information about a specific application.

    Raises:
        404: Application not found
    """
    try:
        registry = get_app_registry()
        app = registry.get_app(name)

        if not app:
            raise HTTPException(
                status_code=404,
                detail=f"Application '{name}' not found"
            )

        return AppInfo(
            name=app.get("name"),
            version=app.get("version"),
            description=app.get("description"),
            category=app.get("category"),
            dependencies=app.get("dependencies", []),
            deploy_method=app.get("deploy_method", "portainer")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get app {name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apps/{name}/deploy", response_model=AppDeployResponse, status_code=status.HTTP_202_ACCEPTED)
async def deploy_app(
    name: str,
    request: AppDeployRequest,
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Deploy application to server (async operation)

    Creates a job for app deployment and returns immediately.
    Use the job_id to track progress.

    Steps performed by the job:
    1. Check app exists in registry
    2. Resolve and deploy dependencies
    3. Deploy application via Portainer or Ansible
    4. Configure DNS (if domain provided)
    5. Run health checks

    Raises:
        404: Application or server not found

    Returns:
        202 Accepted with job_id for tracking
    """
    # Check if app exists in registry
    try:
        registry = get_app_registry()
        app = registry.get_app(name)
        if not app:
            raise HTTPException(
                status_code=404,
                detail=f"Application '{name}' not found in registry"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check app registry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    # Check if server exists
    server_data = orchestrator.storage.state.get_server(request.server_name)
    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{request.server_name}' not found"
        )

    # Determine job type based on deploy_method
    # Infrastructure apps (deploy_method: ansible) use different executor
    deploy_method = app.get("deploy_method", "portainer")

    if deploy_method == "ansible":
        # Infrastructure apps (Portainer, Traefik) deployed via Ansible
        job_type = "deploy_infrastructure"
        logger.info(f"{name} uses ansible deployment method, creating infrastructure job")
    else:
        # Standard apps (PostgreSQL, Redis, N8N) deployed via Portainer API
        job_type = "deploy_app"
        logger.info(f"{name} uses portainer deployment method, creating app job")

    try:
        # Create job with appropriate type
        job = await job_manager.create_job(
            job_type=job_type,
            params={
                "app_name": name,
                "server_name": request.server_name,
                "environment": request.environment or {},
                "domain": request.domain
            }
        )

        logger.info(f"Created job {job.job_id} ({job_type}) for deploying {name} to {request.server_name}")

        # TODO: Start background task to execute job

        return AppDeployResponse(
            job_id=job.job_id,
            message=f"Deployment started for {name} on {request.server_name}",
            app_name=name,
            server_name=request.server_name
        )

    except Exception as e:
        logger.error(f"Failed to create deploy job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apps/{name}/undeploy", response_model=AppUndeployResponse, status_code=status.HTTP_202_ACCEPTED)
async def undeploy_app(
    name: str,
    request: AppDeployRequest,  # Reuse same request model, only server_name needed
    job_manager: JobManager = Depends(get_job_manager),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    Undeploy application from server (async operation)

    Creates a job for app removal and returns immediately.
    Use the job_id to track progress.

    Steps performed by the job:
    1. Stop and remove containers
    2. Remove volumes (optional)
    3. Remove DNS records (if configured)
    4. Update state

    Raises:
        404: Server not found

    Returns:
        202 Accepted with job_id for tracking
    """
    # Check if server exists
    server_data = orchestrator.storage.state.get_server(request.server_name)
    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{request.server_name}' not found"
        )

    try:
        # Create job for app undeployment
        job = await job_manager.create_job(
            job_type="undeploy_app",
            params={
                "app_name": name,
                "server_name": request.server_name
            }
        )

        logger.info(f"Created job {job.job_id} for undeploying {name} from {request.server_name}")

        # TODO: Start background task to execute job

        return AppUndeployResponse(
            job_id=job.job_id,
            message=f"Removal started for {name} on {request.server_name}",
            app_name=name,
            server_name=request.server_name
        )

    except Exception as e:
        logger.error(f"Failed to create undeploy job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_name}/apps", response_model=DeployedAppListResponse)
async def list_deployed_apps(
    server_name: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    List applications deployed on a server

    Returns all applications currently deployed on the specified server.
    Information is retrieved from deployment state.

    Raises:
        404: Server not found
    """
    # Check if server exists
    server_data = orchestrator.storage.state.get_server(server_name)
    if not server_data:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_name}' not found"
        )

    try:
        # Get applications list from server data
        # Applications are stored in the server's 'applications' field
        app_names = server_data.get("applications", [])

        if not app_names:
            return DeployedAppListResponse(
                apps=[],
                server_name=server_name,
                total=0
            )

        # Get app registry for additional details
        registry = get_app_registry()

        # Convert to DeployedAppInfo models
        deployed_apps = []
        for app_name in app_names:
            # Get app definition from registry (if available)
            app_def = registry.get_app(app_name)

            # Build domain based on DNS config and dns_prefix from YAML
            domain = None
            dns_config = server_data.get("dns_config")
            if dns_config:
                zone = dns_config.get("zone_name")
                subdomain = dns_config.get("subdomain")

                # Get dns_prefix from app definition (if exists)
                # Falls back to app_name if no dns_prefix defined
                dns_prefix = app_def.get("dns_prefix") if app_def else None
                prefix_to_use = dns_prefix if dns_prefix else app_name

                if zone:
                    # Domain pattern: {dns_prefix}.{subdomain}.{zone} or {dns_prefix}.{zone}
                    if subdomain:
                        domain = f"{prefix_to_use}.{subdomain}.{zone}"
                    else:
                        domain = f"{prefix_to_use}.{zone}"

            deployed_apps.append(
                DeployedAppInfo(
                    app_name=app_name,
                    server_name=server_name,
                    domain=domain,
                    status="deployed",  # We know it's deployed if it's in the list
                    deployed_at=server_data.get("updated_at"),
                    environment={}  # Environment vars are not stored in state
                )
            )

        return DeployedAppListResponse(
            apps=deployed_apps,
            server_name=server_name,
            total=len(deployed_apps)
        )

    except Exception as e:
        logger.error(f"Failed to list deployed apps: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
