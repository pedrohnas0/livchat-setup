"""
Deployment Manager - Handles application deployments with auto-dependencies

Extracted from orchestrator.py for better modularity (PLAN-08)
"""
import logging
import time
import asyncio
from typing import Optional, Dict, Any, List

try:
    from ..app_registry import AppRegistry
    from ..app_deployer import AppDeployer
    from ..storage import StorageManager
    from ..security_utils import PasswordGenerator
except ImportError:
    from app_registry import AppRegistry
    from app_deployer import AppDeployer
    from storage import StorageManager
    from security_utils import PasswordGenerator

logger = logging.getLogger(__name__)


class DeploymentManager:
    """
    Manages application deployments with automatic dependency resolution

    Responsibilities:
    - Deploy applications with auto-dependency installation
    - Create dependency resources (databases, etc)
    - Manage Portainer/Cloudflare integrations for deployment
    - Handle deployment configuration and secrets
    """

    def __init__(
        self,
        storage: StorageManager,
        app_registry: AppRegistry,
        portainer=None,
        cloudflare=None,
        ssh_manager=None,
        orchestrator=None
    ):
        """
        Initialize DeploymentManager

        Args:
            storage: Storage manager instance
            app_registry: App registry for dependency resolution
            portainer: Optional Portainer client
            cloudflare: Optional Cloudflare client
            ssh_manager: Optional SSH manager for remote operations
            orchestrator: Optional orchestrator reference for infrastructure deployments
        """
        self.storage = storage
        self.app_registry = app_registry
        self.portainer = portainer
        self.cloudflare = cloudflare
        self.ssh_manager = ssh_manager
        self.orchestrator = orchestrator  # For ansible-based deployments
        self.app_deployer = None  # Lazy initialized

    def _ensure_app_deployer(self) -> bool:
        """
        Ensure App Deployer is initialized

        Returns:
            True if App Deployer is ready
        """
        if self.app_deployer:
            return True

        if not self.portainer:
            logger.error("Portainer client not initialized")
            return False

        if not self.cloudflare:
            logger.warning("Cloudflare not configured - DNS setup will be skipped")

        try:
            self.app_deployer = AppDeployer(
                portainer=self.portainer,
                cloudflare=self.cloudflare,
                registry=self.app_registry
            )
            logger.info("App Deployer initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize App Deployer: {e}")
            return False

    async def _deploy_by_method(
        self,
        app_name: str,
        server: Dict[str, Any],
        app_config: Dict[str, Any],
        app_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Route deployment based on deploy_method from app definition

        Args:
            app_name: Name of the app to deploy
            server: Server information dictionary
            app_config: Configuration for deployment
            app_def: App definition from registry

        Returns:
            Deployment result dictionary
        """
        deploy_method = app_def.get("deploy_method", "portainer")
        server_name = server.get("name")

        logger.info(f"Deploying {app_name} using method: {deploy_method}")

        if deploy_method == "ansible":
            # Deploy infrastructure apps via Ansible
            if not self.orchestrator:
                return {
                    "success": False,
                    "error": "Orchestrator reference required for ansible deployments"
                }

            if app_name == "infrastructure":
                # Infrastructure is a bundle - deploy both Traefik and Portainer
                logger.info("Deploying infrastructure bundle (Traefik + Portainer)...")

                # Deploy Traefik first
                traefik_result = await asyncio.to_thread(
                    self.orchestrator.deploy_traefik,
                    server_name=server_name,
                    ssl_email=app_config.get("admin_email", "admin@localhost")
                )

                if not traefik_result:
                    return {
                        "success": False,
                        "error": "Failed to deploy Traefik",
                        "app": "traefik"
                    }

                logger.info("Traefik deployed successfully")

                # Deploy Portainer second
                portainer_result = await asyncio.to_thread(
                    self.orchestrator.deploy_portainer,
                    server_name=server_name,
                    config=app_config
                )

                if not portainer_result:
                    return {
                        "success": False,
                        "error": "Failed to deploy Portainer",
                        "app": "portainer"
                    }

                logger.info("Portainer deployed successfully")

                return {
                    "success": True,
                    "app": app_name,
                    "message": "Infrastructure bundle deployed (Traefik + Portainer)"
                }

            elif app_name == "portainer":
                # Direct Portainer deployment
                result = await asyncio.to_thread(
                    self.orchestrator.deploy_portainer,
                    server_name=server_name,
                    config=app_config
                )

                return {
                    "success": result,
                    "app": app_name,
                    "message": "Portainer deployed" if result else "Portainer deployment failed"
                }

            elif app_name == "traefik":
                # Direct Traefik deployment
                result = await asyncio.to_thread(
                    self.orchestrator.deploy_traefik,
                    server_name=server_name,
                    ssl_email=app_config.get("admin_email", "admin@localhost")
                )

                return {
                    "success": result,
                    "app": app_name,
                    "message": "Traefik deployed" if result else "Traefik deployment failed"
                }

            else:
                return {
                    "success": False,
                    "error": f"Unknown ansible-based app: {app_name}"
                }

        elif deploy_method == "portainer":
            # Deploy via Portainer API
            if not self._ensure_app_deployer():
                return {
                    "success": False,
                    "error": "Failed to initialize App Deployer for Portainer deployment"
                }

            return await self.app_deployer.deploy(server, app_name, app_config)

        else:
            return {
                "success": False,
                "error": f"Unknown deploy_method: {deploy_method}"
            }

    async def deploy_app(
        self,
        server_name: str,
        app_name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Deploy an application to a server with automatic dependency installation

        Args:
            server_name: Name of the server
            app_name: Name of the application
            config: Optional deployment configuration

        Returns:
            Deployment result with dependency info
        """
        logger.info(f"Deploying {app_name} to server {server_name}")

        # Get server
        server = self.storage.state.get_server(server_name)
        if not server:
            return {
                "success": False,
                "error": f"Server {server_name} not found"
            }

        # Resolve dependencies using AppRegistry
        try:
            install_order = self.app_registry.resolve_dependencies(app_name)
            logger.info(f"Dependency resolution: {' -> '.join(install_order)}")
        except ValueError as e:
            return {
                "success": False,
                "error": f"Dependency resolution failed: {str(e)}"
            }

        # Get already-installed apps
        installed_apps = set(server.get("applications", []))
        logger.info(f"Already installed: {installed_apps or 'none'}")

        # Filter out already-installed apps
        apps_to_install = [app for app in install_order if app not in installed_apps]

        if not apps_to_install:
            logger.info(f"{app_name} already deployed!")
            return {
                "success": True,
                "app": app_name,
                "message": "Application already deployed",
                "skipped": True
            }

        logger.info(f"Installing: {' -> '.join(apps_to_install)}")

        # Note: App Deployer initialization moved to _deploy_by_method()
        # to support both ansible and portainer deployment methods

        # Prepare configuration
        if not config:
            config = {}

        # Add default values from storage
        config.setdefault("admin_email", self.storage.state.get_setting("email", "admin@localhost"))
        config.setdefault("network_name", "livchat_network")

        # Auto-install missing dependencies
        installed_in_this_run = []
        for current_app in apps_to_install:
            logger.info(f"Installing {current_app}...")

            # Prepare app-specific config
            app_config = config.copy()

            # Add generated passwords for known apps
            if current_app == "portainer" and "admin_password" not in app_config:
                portainer_password = self.storage.secrets.get_secret(f"portainer_password_{server_name}")
                if not portainer_password:
                    password_gen = PasswordGenerator()
                    portainer_password = password_gen.generate_app_password("portainer", alphanumeric_only=True)
                    self.storage.secrets.set_secret(f"portainer_password_{server_name}", portainer_password)
                app_config["admin_password"] = portainer_password

            # Load passwords for dependencies from vault
            app_def = self.app_registry.get_app(current_app)

            # Build domain from DNS config
            if app_def and "dns_prefix" in app_def:
                dns_config = server.get("dns_config", {})
                zone_name = dns_config.get("zone_name")
                subdomain = dns_config.get("subdomain")

                if zone_name:
                    dns_prefix = app_def["dns_prefix"]

                    # Build domain
                    if subdomain:
                        domain = f"{dns_prefix}.{subdomain}.{zone_name}"
                    else:
                        domain = f"{dns_prefix}.{zone_name}"

                    app_config["domain"] = domain
                    logger.info(f"Built domain for {current_app}: {domain}")

                    # Build additional DNS domains
                    if "additional_dns" in app_def:
                        for additional in app_def["additional_dns"]:
                            additional_prefix = additional.get("prefix")
                            if additional_prefix:
                                if subdomain:
                                    additional_domain = f"{additional_prefix}.{subdomain}.{zone_name}"
                                else:
                                    additional_domain = f"{additional_prefix}.{zone_name}"

                                if additional_prefix == "whk":
                                    app_config["webhook_domain"] = additional_domain
                                    logger.info(f"Built webhook_domain for {current_app}: {additional_domain}")

            if app_def and "dependencies" in app_def:
                for dep in app_def["dependencies"]:
                    password_key = f"{dep}_password"
                    if password_key not in app_config:
                        dep_password = self.storage.secrets.get_secret(password_key)
                        if dep_password:
                            app_config[password_key] = dep_password
                            logger.debug(f"Loaded {dep} password from vault for {current_app}")
                        else:
                            logger.warning(f"Password for dependency '{dep}' not found in vault")

            # Create dependency resources (e.g., PostgreSQL databases)
            if app_def and "dependencies" in app_def:
                for dep in app_def["dependencies"]:
                    if dep == "postgres":
                        database_mapping = {
                            "n8n": "n8n_queue",
                            "chatwoot": "chatwoot_production",
                            "grafana": "grafana",
                            "nocodb": "nocodb"
                        }

                        database_name = database_mapping.get(current_app)
                        if database_name and self.ssh_manager:
                            logger.info(f"Creating PostgreSQL database '{database_name}' for {current_app}")

                            server_ip = server.get("ip")
                            ssh_key_name = server.get("ssh_key", f"{server_name}_key")
                            ssh_key_path = str(self.ssh_manager.get_private_key_path(ssh_key_name))

                            postgres_password = app_config.get("postgres_password")

                            db_result = self.create_dependency_resources(
                                parent_app=current_app,
                                dependency="postgres",
                                config={
                                    "database": database_name,
                                    "password": postgres_password
                                },
                                server_ip=server_ip,
                                ssh_key=ssh_key_path
                            )

                            if db_result.get("success"):
                                logger.info(f"Database '{database_name}' created successfully")
                            else:
                                logger.warning(f"Failed to create database: {db_result.get('error')}")

            # Deploy the current app using appropriate method (ansible or portainer)
            result = await self._deploy_by_method(current_app, server, app_config, app_def)

            if not result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to deploy dependency '{current_app}': {result.get('error')}",
                    "installed_before_failure": installed_in_this_run
                }

            # Save generated passwords to vault
            if current_app in ["postgres", "redis"]:
                password_key = f"{current_app}_password"
                if password_key in app_config:
                    self.storage.secrets.set_secret(password_key, app_config[password_key])
                    logger.info(f"Saved {current_app} password to vault for future use")

                # Wait for containers to be ready
                logger.info(f"Waiting for {current_app} container to be fully ready...")
                time.sleep(15)
                logger.info(f"{current_app} should be ready now")

            # Configure DNS if Cloudflare is configured (only for Portainer-based apps)
            if self.cloudflare and self.app_deployer:
                dns_config = server.get("dns_config", {})
                if dns_config.get("zone_name"):
                    dns_result = await self.app_deployer.configure_dns(
                        server, current_app, dns_config["zone_name"]
                    )
                    if dns_result.get("success"):
                        logger.info(f"DNS configured for {current_app}")

            # Update server state
            apps = server.get("applications", [])
            if current_app not in apps:
                apps.append(current_app)
                server["applications"] = apps
                self.storage.state.update_server(server_name, server)

            installed_in_this_run.append(current_app)
            logger.info(f"{current_app} deployed successfully!")

        return {
            "success": True,
            "app": app_name,
            "message": f"Successfully deployed {app_name} with dependencies",
            "dependencies_resolved": install_order,
            "apps_installed": installed_in_this_run,
            "already_installed": list(installed_apps)
        }

    def create_dependency_resources(
        self,
        parent_app: str,
        dependency: str,
        config: Dict[str, Any],
        server_ip: str,
        ssh_key: str
    ) -> Dict[str, Any]:
        """
        Create dependency resources (e.g., PostgreSQL databases)

        Args:
            parent_app: App that requires the dependency
            dependency: Dependency name (e.g., "postgres")
            config: Resource configuration
            server_ip: Server IP address
            ssh_key: SSH key path

        Returns:
            Result dictionary
        """
        if dependency == "postgres":
            database = config.get("database")
            password = config.get("password")

            if not database or not password:
                return {
                    "success": False,
                    "error": "Database name and password required"
                }

            logger.info(f"Creating PostgreSQL database '{database}' for {parent_app}")

            import subprocess

            create_db_cmd = f"""
                docker exec $(docker ps -qf name=postgres) psql -U postgres -c "CREATE DATABASE {database};"
            """

            try:
                result = subprocess.run(
                    ["ssh", "-i", ssh_key, "-o", "StrictHostKeyChecking=no",
                     f"root@{server_ip}", create_db_cmd],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0 or "already exists" in result.stderr:
                    return {
                        "success": True,
                        "database": database,
                        "message": "Database created or already exists"
                    }
                else:
                    logger.error(f"Failed to create database: {result.stderr}")
                    return {
                        "success": False,
                        "error": f"Database creation failed: {result.stderr}"
                    }

            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Database creation timed out"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Database creation error: {str(e)}"
                }

        return {
            "success": False,
            "error": f"Unsupported dependency: {dependency}"
        }
