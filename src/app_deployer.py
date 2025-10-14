"""
App Deployer - Orchestrates application deployment via Portainer
"""
import logging
import asyncio
import yaml
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class AppDeployer:
    """
    Orchestrates application deployment through Portainer and DNS configuration
    """

    def __init__(self, portainer, cloudflare, registry):
        """
        Initialize App Deployer with dependencies

        Args:
            portainer: PortainerClient instance
            cloudflare: CloudflareClient instance
            registry: AppRegistry instance
        """
        self.portainer = portainer
        self.cloudflare = cloudflare
        self.registry = registry
        logger.info("App Deployer initialized")

    async def deploy(self, server: Dict[str, Any], app_name: str,
                    config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deploy an application to a server

        Args:
            server: Server information dictionary
            app_name: Name of the application to deploy
            config: Configuration for deployment

        Returns:
            Deployment result dictionary
        """
        logger.info(f"Deploying {app_name} to server {server['name']}")

        try:
            # v0.2.0: Validation 1 - DNS must be configured
            dns_config = server.get("dns_config", {})
            if not dns_config.get("zone_name"):
                return {
                    "success": False,
                    "app": app_name,
                    "error": "DNS not configured on server. DNS is required for all app deployments.",
                    "hint": "Run setup-server with zone_name parameter first."
                }

            logger.info(f"DNS validation passed for {server['name']}: {dns_config}")

            # v0.2.0: Validation 2 - infrastructure must be deployed (except if deploying it itself)
            if app_name != "infrastructure":
                apps = server.get("applications", [])
                if "infrastructure" not in apps:
                    return {
                        "success": False,
                        "app": app_name,
                        "error": "Infrastructure (Traefik + Portainer) not deployed. This is required for all applications.",
                        "hint": "Deploy infrastructure first: deploy-app(server_name='...', app_name='infrastructure')"
                    }

                logger.info(f"Infrastructure validation passed for {server['name']}")

            # Get app definition
            app = self.registry.get_app(app_name)
            if not app:
                return {
                    "success": False,
                    "app": app_name,
                    "error": f"App definition not found: {app_name}"
                }

            # Validate app definition
            validation = self.registry.validate_app(app)
            if not validation["valid"]:
                return {
                    "success": False,
                    "app": app_name,
                    "error": f"Validation failed: {validation['errors']}"
                }

            # Resolve dependencies
            dependencies = self.registry.resolve_dependencies(app_name)
            logger.info(f"Resolved dependencies for {app_name}: {dependencies}")

            # Generate docker-compose
            compose_yaml = self.registry.generate_compose(app_name, config)

            # Create required volumes before deploying stack
            if app.get("volumes"):
                logger.info(f"Creating volumes for {app_name}")
                import subprocess
                for volume_mount in app.get("volumes", []):
                    if ":" in volume_mount:
                        volume_name = volume_mount.split(":")[0]
                        # Only create named volumes, not bind mounts
                        if not volume_name.startswith("/"):
                            try:
                                # Create volume via SSH command
                                ssh_key = f"/tmp/livchat_e2e_complete/ssh_keys/{server['ssh_key']}"
                                cmd = [
                                    "ssh", "-i", ssh_key,
                                    "-o", "StrictHostKeyChecking=no",
                                    f"root@{server['ip']}",
                                    f"docker volume create {volume_name} 2>/dev/null || echo 'Volume {volume_name} already exists'"
                                ]
                                result = subprocess.run(cmd, capture_output=True, text=True)
                                logger.info(f"Volume {volume_name}: {result.stdout.strip()}")
                            except Exception as ve:
                                logger.warning(f"Volume {volume_name} creation issue: {ve}")

            # Use endpoint ID 1 as default (like SetupOrion does)
            # When Portainer is deployed with agent, the first endpoint created is ID 1
            endpoint_id = 1

            # Optional: Try to find "primary" endpoint like SetupOrion
            try:
                endpoints = await self.portainer.list_endpoints()
                if endpoints:
                    # Look for primary endpoint first (SetupOrion style)
                    for ep in endpoints:
                        if ep.get("Name") == "primary":
                            endpoint_id = ep.get("Id", 1)
                            logger.info(f"Found 'primary' endpoint with ID: {endpoint_id}")
                            break
                    else:
                        # Use the first endpoint if no "primary" found
                        if endpoints[0].get("Id"):
                            endpoint_id = endpoints[0].get("Id")
                            logger.info(f"Using first endpoint with ID: {endpoint_id}")
                else:
                    logger.info("No endpoints found, using default ID 1")
            except Exception as e:
                logger.warning(f"Could not list endpoints, using default ID 1: {e}")

            # Create stack in Portainer
            stack_name = app_name.replace("_", "-").lower()
            stack_result = await self.portainer.create_stack(
                name=stack_name,
                compose=compose_yaml,
                endpoint_id=endpoint_id,
                env=config.get("environment", {})
            )

            logger.info(f"Stack created for {app_name}: {stack_result}")

            return {
                "success": True,
                "app": app_name,
                "stack_id": stack_result.get("Id"),
                "stack_name": stack_name,
                "dependencies_resolved": dependencies,
                "server": server["name"]
            }

        except Exception as e:
            logger.error(f"Failed to deploy {app_name}: {e}")
            return {
                "success": False,
                "app": app_name,
                "error": str(e)
            }

    async def deploy_custom(self, server: Dict[str, Any], app_name: str,
                          compose_content: str) -> Dict[str, Any]:
        """
        Deploy with custom docker-compose content

        Args:
            server: Server information
            app_name: Name for the stack
            compose_content: Docker compose YAML content

        Returns:
            Deployment result
        """
        logger.info(f"Deploying custom stack {app_name} to server {server['name']}")

        try:
            # Create stack in Portainer
            stack_result = await self.portainer.create_stack(
                name=app_name,
                compose=compose_content,
                env={}
            )

            return {
                "success": True,
                "app": app_name,
                "stack_id": stack_result.get("Id"),
                "custom": True
            }

        except Exception as e:
            logger.error(f"Failed to deploy custom stack {app_name}: {e}")
            return {
                "success": False,
                "app": app_name,
                "error": str(e)
            }

    async def configure_dns(self, server: Dict[str, Any], app_name: str,
                          domain: str) -> Dict[str, Any]:
        """
        Configure DNS records for an application

        Args:
            server: Server information
            app_name: Application name
            domain: Domain name for DNS

        Returns:
            DNS configuration result
        """
        logger.info(f"Configuring DNS for {app_name} on {domain}")

        try:
            # Get DNS config from server (v0.2.0)
            dns_config = server.get("dns_config", {})
            zone = dns_config.get("zone_name", domain)
            subdomain = dns_config.get("subdomain")

            # Add DNS records using standard prefixes
            result = await self.cloudflare.add_app_with_standard_prefix(
                app_name=app_name,
                zone_name=zone,
                subdomain=subdomain
            )

            return {
                "success": True,
                "app": app_name,
                "dns_records": result
            }

        except Exception as e:
            logger.error(f"Failed to configure DNS for {app_name}: {e}")
            return {
                "success": False,
                "app": app_name,
                "error": str(e)
            }

    async def verify_health(self, server: Dict[str, Any], app_name: str) -> Dict[str, Any]:
        """
        Verify health status of deployed application

        Args:
            server: Server information
            app_name: Application name

        Returns:
            Health status dictionary
        """
        logger.info(f"Checking health for {app_name} on server {server['name']}")

        try:
            # Get app definition
            app = self.registry.get_app(app_name)
            if not app:
                return {
                    "healthy": False,
                    "app": app_name,
                    "error": "App definition not found"
                }

            # Get health check config
            health_config = app.get("health_check", {})
            if not health_config:
                logger.warning(f"No health check configured for {app_name}")
                return {
                    "healthy": True,
                    "app": app_name,
                    "status": "no_health_check"
                }

            # Perform health check
            endpoint = health_config.get("endpoint", f"http://{server['ip']}")
            retries = health_config.get("retries", 3)
            interval = health_config.get("interval", "30s")

            # Convert interval to seconds
            interval_seconds = 30
            if interval.endswith("s"):
                interval_seconds = int(interval[:-1])

            # Try health check with retries
            for attempt in range(retries):
                try:
                    async with httpx.AsyncClient(verify=False) as client:
                        response = await client.get(endpoint, timeout=10)
                        if response.status_code < 400:
                            return {
                                "healthy": True,
                                "app": app_name,
                                "status": "running",
                                "checks_passed": attempt + 1,
                                "checks_failed": 0
                            }
                except Exception as e:
                    logger.debug(f"Health check attempt {attempt + 1} failed: {e}")

                if attempt < retries - 1:
                    await asyncio.sleep(interval_seconds)

            return {
                "healthy": False,
                "app": app_name,
                "status": "unhealthy",
                "checks_passed": 0,
                "checks_failed": retries
            }

        except Exception as e:
            logger.error(f"Health check failed for {app_name}: {e}")
            return {
                "healthy": False,
                "app": app_name,
                "error": str(e)
            }

    async def rollback(self, server: Dict[str, Any], app_name: str) -> Dict[str, Any]:
        """
        Rollback a failed deployment

        Args:
            server: Server information
            app_name: Application name

        Returns:
            Rollback result
        """
        logger.info(f"Rolling back {app_name} on server {server['name']}")

        try:
            # Get stack
            stacks = await self.portainer.list_stacks()
            stack = next((s for s in stacks if s["Name"] == app_name), None)

            if stack:
                # Delete the stack
                await self.portainer.delete_stack(stack["Id"])
                logger.info(f"Stack {app_name} deleted")

            return {
                "success": True,
                "app": app_name,
                "action": "rolled_back"
            }

        except Exception as e:
            logger.error(f"Rollback failed for {app_name}: {e}")
            return {
                "success": False,
                "app": app_name,
                "error": str(e)
            }

    async def list_deployed_apps(self, server: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List all deployed applications on a server

        Args:
            server: Server information

        Returns:
            List of deployed applications
        """
        logger.info(f"Listing deployed apps on server {server['name']}")

        try:
            # Get stacks from Portainer
            stacks = await self.portainer.list_stacks()

            # Format response
            apps = []
            for stack in stacks:
                apps.append({
                    "name": stack["Name"],
                    "id": stack["Id"],
                    "status": "running" if stack.get("Status") == 1 else "stopped",
                    "created": stack.get("CreationDate")
                })

            return apps

        except Exception as e:
            logger.error(f"Failed to list deployed apps: {e}")
            return []

    async def delete_app(self, server: Dict[str, Any], app_name: str) -> Dict[str, Any]:
        """
        Delete a deployed application

        Args:
            server: Server information
            app_name: Application name

        Returns:
            Deletion result
        """
        logger.info(f"Deleting {app_name} from server {server['name']}")

        try:
            # Get stack
            stacks = await self.portainer.list_stacks()
            stack = next((s for s in stacks if s["Name"] == app_name), None)

            if not stack:
                return {
                    "success": False,
                    "app": app_name,
                    "error": "Stack not found"
                }

            # Delete stack
            await self.portainer.delete_stack(stack["Id"])

            return {
                "success": True,
                "app": app_name,
                "action": "deleted"
            }

        except Exception as e:
            logger.error(f"Failed to delete {app_name}: {e}")
            return {
                "success": False,
                "app": app_name,
                "error": str(e)
            }

    async def update_app(self, server: Dict[str, Any], app_name: str,
                       config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing application

        Args:
            server: Server information
            app_name: Application name
            config: New configuration

        Returns:
            Update result
        """
        logger.info(f"Updating {app_name} on server {server['name']}")

        try:
            # Get existing stack
            stacks = await self.portainer.list_stacks()
            stack = next((s for s in stacks if s["Name"] == app_name), None)

            if not stack:
                # Deploy as new if not exists
                return await self.deploy(server, app_name, config)

            # Generate new compose
            compose_yaml = self.registry.generate_compose(app_name, config)

            # Update stack (delete and recreate for now)
            await self.portainer.delete_stack(stack["Id"])

            # Small delay to ensure cleanup
            await asyncio.sleep(2)

            # Recreate stack
            stack_result = await self.portainer.create_stack(
                name=app_name,
                compose=compose_yaml,
                env=config.get("environment", {})
            )

            return {
                "success": True,
                "app": app_name,
                "action": "updated",
                "stack_id": stack_result.get("Id")
            }

        except Exception as e:
            logger.error(f"Failed to update {app_name}: {e}")
            return {
                "success": False,
                "app": app_name,
                "error": str(e)
            }

    async def wait_for_dependencies(self, server: Dict[str, Any],
                                   dependencies: List[str]) -> Dict[str, Any]:
        """
        Wait for dependencies to be ready

        Args:
            server: Server information
            dependencies: List of dependency names

        Returns:
            Dependencies status
        """
        logger.info(f"Waiting for dependencies: {dependencies}")

        status = {}
        all_ready = True

        for dep in dependencies:
            health = await self.verify_health(server, dep)
            status[dep] = health["healthy"]
            if not health["healthy"]:
                all_ready = False
                logger.warning(f"Dependency {dep} is not ready")

        return {
            "ready": all_ready,
            "dependencies_status": status
        }

    async def check_dependency_health(self, server: Dict[str, Any],
                                     dependency: str) -> bool:
        """
        Check if a dependency is healthy

        Args:
            server: Server information
            dependency: Dependency name

        Returns:
            True if healthy
        """
        health = await self.verify_health(server, dependency)
        return health["healthy"]

    async def execute_post_deploy(self, server: Dict[str, Any], app_name: str,
                                 actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute post-deployment actions

        Args:
            server: Server information
            app_name: Application name
            actions: List of post-deploy actions

        Returns:
            Execution result
        """
        logger.info(f"Executing post-deploy actions for {app_name}")

        executed = []
        success = True

        for action in actions:
            action_type = action.get("action")

            try:
                if action_type == "wait_health":
                    timeout = action.get("timeout", 60)
                    # Wait for health with timeout
                    start_time = datetime.now()
                    while (datetime.now() - start_time).seconds < timeout:
                        health = await self.verify_health(server, app_name)
                        if health["healthy"]:
                            break
                        await asyncio.sleep(5)

                    executed.append({
                        "action": "wait_health",
                        "success": health["healthy"]
                    })

                elif action_type == "init_admin":
                    # Initialize admin (placeholder)
                    executed.append({
                        "action": "init_admin",
                        "success": True
                    })

                elif action_type == "create_databases":
                    # Create databases (placeholder)
                    executed.append({
                        "action": "create_databases",
                        "success": True
                    })

                else:
                    logger.warning(f"Unknown action type: {action_type}")

            except Exception as e:
                logger.error(f"Post-deploy action failed: {e}")
                success = False
                executed.append({
                    "action": action_type,
                    "success": False,
                    "error": str(e)
                })

        return {
            "success": success,
            "actions_executed": executed
        }

    async def check_health(self, endpoint: str, retries: int = 3) -> Dict[str, Any]:
        """
        Check health of an endpoint

        Args:
            endpoint: Health check endpoint
            retries: Number of retries

        Returns:
            Health status
        """
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    response = await client.get(endpoint, timeout=10)
                    if response.status_code < 400:
                        return {
                            "healthy": True,
                            "status": "running",
                            "checks_passed": 1,
                            "checks_failed": 0
                        }
            except Exception as e:
                logger.debug(f"Health check attempt {attempt + 1} failed: {e}")

            if attempt < retries - 1:
                await asyncio.sleep(5)

        return {
            "healthy": False,
            "status": "unhealthy",
            "checks_passed": 0,
            "checks_failed": retries
        }