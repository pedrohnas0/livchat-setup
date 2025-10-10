"""Core orchestration and dependency resolution for LivChat Setup"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from .storage import StorageManager
    from .providers.hetzner import HetznerProvider
    from .ssh_manager import SSHKeyManager
    from .ansible_executor import AnsibleRunner
    from .server_setup import ServerSetup
    from .security_utils import CredentialsManager, PasswordGenerator
    from .integrations.cloudflare import CloudflareClient
    from .integrations.portainer import PortainerClient
    from .app_registry import AppRegistry
    from .app_deployer import AppDeployer
except ImportError:
    # For direct execution
    from storage import StorageManager
    from providers.hetzner import HetznerProvider
    from ssh_manager import SSHKeyManager
    from ansible_executor import AnsibleRunner
    from server_setup import ServerSetup
    from security_utils import CredentialsManager, PasswordGenerator
    from integrations.cloudflare import CloudflareClient
    from integrations.portainer import PortainerClient
    from app_registry import AppRegistry
    from app_deployer import AppDeployer

logger = logging.getLogger(__name__)


class DependencyResolver:
    """Resolves and manages application dependencies"""

    def __init__(self):
        """Initialize DependencyResolver"""
        # Hardcoded dependencies for now - will load from YAML later
        self.dependencies = {
            "n8n": ["postgres", "redis"],
            "chatwoot": ["postgres", "redis", "sidekiq"],
            "wordpress": ["mysql"],
            "grafana": ["postgres"],
            "nocodb": ["postgres"],
        }

    def resolve_install_order(self, apps: List[str]) -> List[str]:
        """
        Resolve installation order based on dependencies

        Args:
            apps: List of applications to install

        Returns:
            Ordered list of applications to install (dependencies first)
        """
        resolved = []
        to_resolve = apps.copy()

        # Collect all dependencies needed
        all_deps = set()
        for app in apps:
            deps = self.dependencies.get(app, [])
            all_deps.update(deps)

        # Add dependencies that aren't in the original list
        for dep in all_deps:
            if dep not in to_resolve:
                to_resolve.append(dep)

        while to_resolve:
            # Find apps with no unresolved dependencies
            can_install = []
            for app in to_resolve:
                deps = self.dependencies.get(app, [])
                # Check if all dependencies are resolved
                if all(dep in resolved for dep in deps):
                    can_install.append(app)

            if not can_install:
                # Circular dependency or missing dependency
                logger.warning(f"Cannot resolve dependencies for: {to_resolve}")
                break

            # Add resolvable apps to resolved list
            for app in can_install:
                if app not in resolved:
                    resolved.append(app)
                    to_resolve.remove(app)

        return resolved

    def validate_dependencies(self, app: str) -> Dict[str, Any]:
        """
        Validate if an application's dependencies can be satisfied

        Args:
            app: Application name

        Returns:
            Validation result with status and details
        """
        result = {
            "valid": True,
            "app": app,
            "dependencies": [],
            "missing": [],
            "errors": []
        }

        deps = self.dependencies.get(app, [])
        result["dependencies"] = deps

        # For now, just return the dependencies
        # In the future, check if they're installed or available

        return result

    def get_dependencies(self, app: str) -> List[str]:
        """
        Get dependencies for an application

        Args:
            app: Application name

        Returns:
            List of dependencies
        """
        return self.dependencies.get(app, [])

    def configure_dependency(self, parent_app: str, dependency: str) -> Dict[str, Any]:
        """
        Configure a dependency for a parent application

        Args:
            parent_app: Parent application name
            dependency: Dependency name

        Returns:
            Configuration details
        """
        # This will be expanded to handle actual configuration
        # For now, return a placeholder
        config = {
            "parent": parent_app,
            "dependency": dependency,
            "status": "configured"
        }

        # Example configurations
        if dependency == "postgres" and parent_app == "n8n":
            config["database"] = "n8n_queue"
            config["user"] = "n8n_user"
        elif dependency == "redis" and parent_app == "n8n":
            config["db"] = 1

        return config

    def create_dependency_resources(self, parent_app: str, dependency: str,
                                   config: Dict[str, Any],
                                   server_ip: str, ssh_key: str) -> Dict[str, Any]:
        """
        Create actual resources for a dependency (e.g., PostgreSQL database)

        Args:
            parent_app: Parent application name
            dependency: Dependency name (e.g., "postgres")
            config: Configuration with database, user, password
            server_ip: Server IP address
            ssh_key: Path to SSH key file

        Returns:
            Result dictionary with success status
        """
        import subprocess

        logger.info(f"Creating resources for {dependency} dependency of {parent_app}")

        if dependency == "postgres":
            # Create PostgreSQL database via docker exec
            database = config.get("database")
            password = config.get("password")

            if not database:
                return {
                    "success": False,
                    "error": "Database name not specified"
                }

            try:
                # Find postgres container name in swarm
                find_container_cmd = [
                    "ssh", "-i", ssh_key,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"root@{server_ip}",
                    "docker ps --filter name=postgres --format '{{.Names}}' | head -1"
                ]

                container_result = subprocess.run(
                    find_container_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if container_result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to find postgres container: {container_result.stderr}"
                    }

                container_name = container_result.stdout.strip()
                if not container_name:
                    return {
                        "success": False,
                        "error": "Postgres container not found"
                    }

                logger.info(f"Found postgres container: {container_name}")

                # Create database using createdb (simpler and safer than raw SQL)
                create_db_cmd = [
                    "ssh", "-i", ssh_key,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    f"root@{server_ip}",
                    f"docker exec {container_name} createdb -U postgres {database} || echo 'Database may already exist'"
                ]

                result = subprocess.run(
                    create_db_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                logger.info(f"Create database output: {result.stdout}")

                return {
                    "success": True,
                    "database": database,
                    "container": container_name,
                    "output": result.stdout
                }

            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Command timed out"
                }
            except Exception as e:
                logger.error(f"Failed to create database: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }

        return {
            "success": False,
            "error": f"Resource creation not implemented for {dependency}"
        }


class Orchestrator:
    """Main orchestrator for LivChat Setup system"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize Orchestrator

        Args:
            config_dir: Custom config directory (default: ~/.livchat)
        """
        self.config_dir = config_dir or Path.home() / ".livchat"
        self.storage = StorageManager(self.config_dir)
        self.resolver = DependencyResolver()
        self.provider = None

        # Initialize new components
        self.ssh_manager = SSHKeyManager(self.storage)
        self.credentials = CredentialsManager(self.storage)
        self.ansible_runner = AnsibleRunner(self.ssh_manager)
        self.server_setup = ServerSetup(self.ansible_runner, self.storage)

        # Initialize integration clients
        self.cloudflare = None  # Will be initialized with configure_cloudflare()
        self.portainer = None   # Will be initialized per server

        # Initialize app management components
        self.app_registry = AppRegistry()
        self.app_deployer = None  # Will be initialized when needed

        # Load app definitions if available
        apps_dir = Path(__file__).parent.parent / "apps" / "definitions"
        if apps_dir.exists():
            try:
                self.app_registry.load_definitions(str(apps_dir))
                logger.info(f"Loaded {len(self.app_registry.apps)} app definitions")
            except Exception as e:
                logger.warning(f"Could not load app definitions: {e}")

        # Auto-load existing data if available
        if self.config_dir.exists():
            try:
                self.storage.config.load()
                self.storage.state.load()
                logger.info("Loaded existing configuration and state")

                # Try to initialize Cloudflare if credentials exist
                self._init_cloudflare_from_config()
            except Exception as e:
                logger.debug(f"Could not load existing data: {e}")

        logger.info(f"Orchestrator initialized with config dir: {self.config_dir}")

    def init(self) -> None:
        """Initialize configuration directory and files"""
        logger.info("Initializing LivChat Setup...")
        self.storage.init()

        # Set default admin email if not configured
        if not self.storage.config.get("admin_email"):
            default_email = os.environ.get("CLOUDFLARE_EMAIL", "pedrohnas0@gmail.com")
            self.storage.config.set("admin_email", default_email)
            logger.info(f"Set default admin email: {default_email}")

        logger.info("Initialization complete")

    def configure_provider(self, provider_name: str, token: str) -> None:
        """
        Configure a cloud provider

        Args:
            provider_name: Name of the provider (e.g., 'hetzner')
            token: API token for the provider
        """
        logger.info(f"Configuring provider: {provider_name}")

        # Save token securely
        self.storage.secrets.set_secret(f"{provider_name}_token", token)

        # Update config
        self.storage.config.set("provider", provider_name)

        # Initialize provider
        if provider_name == "hetzner":
            self.provider = HetznerProvider(token)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

        logger.info(f"Provider {provider_name} configured successfully")

    def _init_cloudflare_from_config(self) -> bool:
        """
        Initialize Cloudflare client from saved configuration

        Returns:
            True if initialized successfully
        """
        try:
            email = self.storage.secrets.get_secret("cloudflare_email")
            api_key = self.storage.secrets.get_secret("cloudflare_api_key")

            if email and api_key:
                self.cloudflare = CloudflareClient(email, api_key)
                logger.info("Cloudflare client initialized from saved credentials")
                return True
        except Exception as e:
            logger.debug(f"Could not initialize Cloudflare: {e}")

        return False

    def configure_cloudflare(self, email: str, api_key: str) -> bool:
        """
        Configure Cloudflare API credentials

        Args:
            email: Cloudflare account email
            api_key: Global API Key from Cloudflare dashboard

        Returns:
            True if successful
        """
        logger.info(f"Configuring Cloudflare with email: {email}")

        try:
            # Test the credentials by initializing the client
            self.cloudflare = CloudflareClient(email, api_key)

            # Save credentials securely in vault
            self.storage.secrets.set_secret("cloudflare_email", email)
            self.storage.secrets.set_secret("cloudflare_api_key", api_key)

            logger.info("Cloudflare configured successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to configure Cloudflare: {e}")
            self.cloudflare = None
            return False

    def create_server(self, name: str, server_type: str, region: str,
                     image: str = "ubuntu-22.04") -> Dict[str, Any]:
        """
        Create a new server

        Args:
            name: Server name
            server_type: Server type (e.g., 'cx21')
            region: Region/location (e.g., 'nbg1')
            image: OS image (default: 'ubuntu-22.04')

        Returns:
            Server information dictionary
        """
        if not self.provider:
            # Try to load provider from config
            provider_name = self.storage.config.get("provider")
            if provider_name == "hetzner":
                token = self.storage.secrets.get_secret("hetzner_token")
                if not token:
                    raise RuntimeError("Hetzner token not found. Run configure_provider first.")
                self.provider = HetznerProvider(token)
            else:
                raise RuntimeError("No provider configured. Run configure_provider first.")

        logger.info(f"Creating server: {name} ({server_type} in {region} with {image})")

        # Generate SSH key for the server BEFORE creating it
        key_name = f"{name}_key"
        logger.debug(f"Checking if SSH key exists: {key_name}")
        key_exists = self.ssh_manager.key_exists(key_name)
        logger.debug(f"SSH key {key_name} exists locally: {key_exists}")

        # Generate key if it doesn't exist locally
        if not key_exists:
            logger.info(f"Generating SSH key for {name}")
            key_info = self.ssh_manager.generate_key_pair(key_name)
            logger.info(f"SSH key generated: {key_name}")

        # Always ensure the key is added to Hetzner
        token = self.storage.secrets.get_secret(f"{self.storage.config.get('provider', 'hetzner')}_token")
        if token:
            logger.info(f"Ensuring SSH key {key_name} is added to Hetzner...")
            success = self.ssh_manager.add_to_hetzner(key_name, token)
            if not success:
                logger.error(f"❌ Failed to add SSH key {key_name} to Hetzner")
                # Should we continue without SSH access?
                raise RuntimeError(f"Cannot add SSH key to Hetzner - server would be inaccessible")
            else:
                logger.info(f"✅ SSH key {key_name} is available in Hetzner")
                # Small delay to ensure key is available
                import time
                time.sleep(2)
        else:
            logger.error("No Hetzner token available to add SSH key")
            raise RuntimeError("Cannot add SSH key without Hetzner token")

        # Create server with SSH key
        server = self.provider.create_server(name, server_type, region,
                                            image=image, ssh_keys=[key_name])

        # Add SSH key info to server data
        server["ssh_key"] = key_name

        # Save to state
        self.storage.state.add_server(name, server)

        logger.info(f"Server {name} created successfully: {server['ip']}")
        return server

    async def setup_dns_for_server(self, server_name: str, zone_name: str,
                                  subdomain: Optional[str] = None) -> Dict[str, Any]:
        """
        Setup DNS records for a server (Portainer A record)

        Args:
            server_name: Name of the server
            zone_name: Cloudflare zone name (e.g., "livchat.ai")
            subdomain: Optional subdomain (e.g., "lab", "dev")

        Returns:
            Result dictionary with DNS setup status
        """
        if not self.cloudflare:
            return {
                "success": False,
                "error": "Cloudflare not configured. Run configure_cloudflare first."
            }

        server = self.get_server(server_name)
        if not server:
            return {
                "success": False,
                "error": f"Server {server_name} not found"
            }

        try:
            # Setup DNS A record for Portainer
            result = await self.cloudflare.setup_server_dns(
                server={"name": server_name, "ip": server["ip"]},
                zone_name=zone_name,
                subdomain=subdomain
            )

            if result["success"]:
                # Save DNS info to state (only zone and subdomain)
                dns_info = {
                    "zone": zone_name,
                    "subdomain": subdomain
                }
                server["dns"] = dns_info
                self.storage.state.update_server(server_name, server)

                logger.info(f"DNS configured for server {server_name}: {result['record_name']}")

            return result

        except Exception as e:
            logger.error(f"Failed to setup DNS: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def add_app_dns(self, app_name: str, zone_name: str,
                        subdomain: Optional[str] = None) -> Dict[str, Any]:
        """
        Add DNS records for an application

        Args:
            app_name: Application name (e.g., "chatwoot", "n8n")
            zone_name: Cloudflare zone name
            subdomain: Optional subdomain

        Returns:
            Result dictionary with DNS setup status
        """
        if not self.cloudflare:
            return {
                "success": False,
                "error": "Cloudflare not configured. Run configure_cloudflare first."
            }

        try:
            # Use standard prefix mapping for the app
            results = await self.cloudflare.add_app_with_standard_prefix(
                app_name=app_name,
                zone_name=zone_name,
                subdomain=subdomain
            )

            # Return summary
            success_count = sum(1 for r in results if r.get("success"))
            return {
                "success": success_count > 0,
                "app": app_name,
                "records_created": success_count,
                "details": results
            }

        except Exception as e:
            logger.error(f"Failed to add app DNS: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """List all managed servers"""
        return self.storage.state.list_servers()

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """Get server by name"""
        return self.storage.state.get_server(name)

    def delete_server(self, name: str) -> bool:
        """
        Delete a server

        Args:
            name: Server name

        Returns:
            True if successful
        """
        logger.info(f"Deleting server: {name}")

        server = self.storage.state.get_server(name)
        if not server:
            logger.warning(f"Server {name} not found in state")
            return False

        if not self.provider:
            # Try to load provider from config
            provider_name = server.get("provider", self.storage.config.get("provider"))
            if provider_name == "hetzner":
                token = self.storage.secrets.get_secret("hetzner_token")
                if token:
                    self.provider = HetznerProvider(token)

        # Delete from provider
        if self.provider and "id" in server:
            try:
                self.provider.delete_server(server["id"])
            except Exception as e:
                logger.error(f"Failed to delete server from provider: {e}")

        # Remove from state regardless
        self.storage.state.remove_server(name)

        logger.info(f"Server {name} deleted successfully")
        return True

    def deploy_apps(self, server_name: str, apps: List[str]) -> Dict[str, Any]:
        """
        Deploy applications to a server with dependency resolution

        Args:
            server_name: Target server name
            apps: List of applications to deploy

        Returns:
            Deployment result
        """
        server = self.get_server(server_name)
        if not server:
            raise ValueError(f"Server {server_name} not found")

        # Resolve installation order
        install_order = self.resolver.resolve_install_order(apps)

        logger.info(f"Resolved installation order: {install_order}")

        # For now, just return the plan
        # In the future, this will actually deploy
        result = {
            "server": server_name,
            "requested_apps": apps,
            "install_order": install_order,
            "status": "planned"
        }

        # Add to deployment history
        self.storage.state.add_deployment({
            "server": server_name,
            "apps": install_order,
            "status": "planned"
        })

        return result

    def validate_app_dependencies(self, app: str) -> Dict[str, Any]:
        """
        Validate application dependencies

        Args:
            app: Application name

        Returns:
            Validation result
        """
        return self.resolver.validate_dependencies(app)

    def setup_server_ssh(self, server_name: str) -> bool:
        """
        Setup SSH key for a server

        Args:
            server_name: Name of the server

        Returns:
            True if successful
        """
        server = self.get_server(server_name)
        if not server:
            logger.error(f"Server {server_name} not found")
            return False

        # Generate SSH key if not exists
        key_name = f"{server_name}_key"
        if not self.ssh_manager.key_exists(key_name):
            logger.info(f"Generating SSH key for {server_name}")
            key_info = self.ssh_manager.generate_key_pair(key_name)

            # Save key name in server state
            server["ssh_key"] = key_name
            self.storage.state.update_server(server_name, server)

            # Add to provider if configured
            if self.provider and hasattr(self.provider, 'add_ssh_key'):
                token = self.storage.secrets.get_secret(f"{server.get('provider', 'hetzner')}_token")
                if token:
                    self.ssh_manager.add_to_hetzner(key_name, token)

        return True

    def setup_server(self, server_name: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run complete server setup

        Args:
            server_name: Name of the server
            config: Optional configuration overrides

        Returns:
            Setup result
        """
        server = self.get_server(server_name)
        if not server:
            raise ValueError(f"Server {server_name} not found")

        logger.info(f"Starting setup for server {server_name}")

        # Ensure SSH key is configured
        if not self.setup_server_ssh(server_name):
            return {
                "success": False,
                "message": "Failed to setup SSH key",
                "server": server_name
            }

        # Run full setup through ServerSetup
        result = self.server_setup.full_setup(server, config)

        # Update state with setup status
        if result.success:
            server["setup_status"] = "complete"
            server["setup_date"] = result.timestamp.isoformat()
        else:
            server["setup_status"] = f"failed_at_{result.step}"
            server["setup_error"] = result.message

        self.storage.state.update_server(server_name, server)

        return {
            "success": result.success,
            "message": result.message,
            "server": server_name,
            "step": result.step,
            "details": result.details
        }

    def install_docker(self, server_name: str) -> bool:
        """
        Install Docker on a server

        Args:
            server_name: Name of the server

        Returns:
            True if successful
        """
        server = self.get_server(server_name)
        if not server:
            return False

        result = self.server_setup.install_docker(server)
        return result.success

    def init_swarm(self, server_name: str, network_name: str = "livchat_network") -> bool:
        """
        Initialize Docker Swarm on a server

        Args:
            server_name: Name of the server
            network_name: Name for the overlay network

        Returns:
            True if successful
        """
        server = self.get_server(server_name)
        if not server:
            return False

        result = self.server_setup.init_swarm(server, network_name)
        return result.success

    def deploy_traefik(self, server_name: str, ssl_email: str = None) -> bool:
        """
        Deploy Traefik on a server

        Args:
            server_name: Name of the server
            ssl_email: Email for Let's Encrypt SSL

        Returns:
            True if successful
        """
        server = self.get_server(server_name)
        if not server:
            return False

        config = {}
        if ssl_email:
            config["ssl_email"] = ssl_email

        result = self.server_setup.deploy_traefik(server, config)
        return result.success

    def deploy_portainer(self, server_name: str, config: Dict = None) -> bool:
        """
        Deploy Portainer CE on a server with automatic admin initialization

        Args:
            server_name: Name of the server
            config: Portainer configuration (admin_password, https_port, etc)

        Returns:
            True if successful
        """
        server = self.get_server(server_name)
        if not server:
            logger.error(f"Server {server_name} not found")
            return False

        logger.info(f"Deploying Portainer on server {server_name}")

        # Deploy Portainer
        result = self.server_setup.deploy_portainer(server, config or {})

        if result.success:
            logger.info(f"Portainer deployed successfully on {server_name}")

            # Update server state
            apps = self.storage.state.get_server(server_name).get('applications', [])
            if 'portainer' not in apps:
                apps.append('portainer')
                self.storage.state.update_server(server_name, {'applications': apps})

            # Automatic Portainer initialization
            logger.info("Initializing Portainer admin account...")

            # Get server IP
            server_ip = server.get("ip")

            # Get credentials from vault (should have been saved during deployment)
            admin_email = self.storage.config.get("admin_email", "admin@localhost")
            portainer_password = self.storage.secrets.get_secret(f"portainer_password_{server_name}")

            if not portainer_password:
                # This should not happen if deployment was successful
                logger.error(f"Portainer password not found in vault for {server_name}")
                logger.error("This indicates a problem during deployment")
                return False

            # Create temporary Portainer client for initialization
            # NOTE: Portainer initial admin is always 'admin', we can update later via API
            portainer_client = PortainerClient(
                url=f"https://{server_ip}:9443",
                username="admin",  # Portainer requires 'admin' for initial setup
                password=portainer_password
            )

            # Wait for Portainer to be ready
            import asyncio
            ready = asyncio.run(portainer_client.wait_for_ready(max_attempts=30, delay=10))

            if ready:
                # Initialize admin account
                initialized = asyncio.run(portainer_client.initialize_admin())

                if initialized:
                    logger.info(f"✅ Portainer admin initialized successfully!")
                    logger.info(f"   Access URL: https://{server_ip}:9443")
                    logger.info(f"   Username: {admin_email}")
                    logger.info(f"   Password stored in vault: portainer_password_{server_name}")
                    logger.info(f"⚠️  NOTE: Portainer endpoint will be created automatically on first login")
                else:
                    logger.warning("Portainer admin initialization returned false (may already be initialized)")
            else:
                logger.error("Portainer did not become ready within timeout period")
                return False

        return result.success

    def _init_portainer_for_server(self, server_name: str) -> bool:
        """
        Initialize Portainer client for a specific server

        Args:
            server_name: Name of the server

        Returns:
            True if initialized successfully
        """
        server = self.get_server(server_name)
        if not server:
            logger.error(f"Server {server_name} not found")
            return False

        # Get server IP
        server_ip = server.get("ip")
        if not server_ip:
            logger.error(f"Server {server_name} has no IP address")
            return False

        # Get Portainer credentials from vault
        portainer_password = self.storage.secrets.get_secret(f"portainer_password_{server_name}")
        admin_email = self.storage.config.get("admin_email", "admin@localhost")

        if not portainer_password:
            # Password should have been saved during deployment
            logger.error(f"Portainer password not found in vault for {server_name}")
            logger.error("This indicates the deployment did not save the password correctly")
            return False

        try:
            # Initialize Portainer client
            # NOTE: Portainer currently only supports 'admin' as initial username
            # We save the email for future use but use 'admin' for now
            self.portainer = PortainerClient(
                url=f"https://{server_ip}:9443",
                username="admin",  # Portainer requires 'admin' as initial username
                password=portainer_password
            )
            logger.info(f"Portainer client initialized for server {server_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Portainer client: {e}")
            return False

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

    async def deploy_app(self, server_name: str, app_name: str,
                        config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Deploy an application to a server

        Args:
            server_name: Name of the server
            app_name: Name of the application
            config: Optional deployment configuration

        Returns:
            Deployment result
        """
        logger.info(f"Deploying {app_name} to server {server_name}")

        # Get server
        server = self.get_server(server_name)
        if not server:
            return {
                "success": False,
                "error": f"Server {server_name} not found"
            }

        # Initialize Portainer if needed
        if not self.portainer:
            if not self._init_portainer_for_server(server_name):
                return {
                    "success": False,
                    "error": "Failed to initialize Portainer client"
                }

        # Ensure App Deployer is ready
        if not self._ensure_app_deployer():
            return {
                "success": False,
                "error": "Failed to initialize App Deployer"
            }

        # Prepare configuration
        if not config:
            config = {}

        # Add default values from storage
        config.setdefault("admin_email", self.storage.config.get("admin_email", "admin@localhost"))
        config.setdefault("network_name", "livchat_network")

        # Add generated passwords for known apps
        if app_name == "portainer" and "admin_password" not in config:
            portainer_password = self.storage.secrets.get_secret(f"portainer_password_{server_name}")
            if not portainer_password:
                # Generate alphanumeric password to avoid shell/Docker issues
                password_gen = PasswordGenerator()
                portainer_password = password_gen.generate_app_password("portainer", alphanumeric_only=True)
                self.storage.secrets.set_secret(f"portainer_password_{server_name}", portainer_password)
            config["admin_password"] = portainer_password

        # Load passwords for dependencies from vault
        # This ensures apps like N8N can connect to postgres/redis
        app_def = self.app_registry.get_app(app_name)
        if app_def and "dependencies" in app_def:
            for dep in app_def["dependencies"]:
                # Load password for each dependency (postgres, redis, etc)
                password_key = f"{dep}_password"
                if password_key not in config:
                    # Try to load from vault (should have been saved when dependency was deployed)
                    dep_password = self.storage.secrets.get_secret(password_key)
                    if dep_password:
                        config[password_key] = dep_password
                        logger.debug(f"Loaded {dep} password from vault for {app_name}")
                    else:
                        logger.warning(f"Password for dependency '{dep}' not found in vault")

        # Create dependency resources (e.g., PostgreSQL databases) before deploying app
        if app_def and "dependencies" in app_def:
            for dep in app_def["dependencies"]:
                if dep == "postgres":
                    # Determine database name based on app
                    # This mapping should eventually come from app definitions
                    database_mapping = {
                        "n8n": "n8n_queue",
                        "chatwoot": "chatwoot_production",
                        "grafana": "grafana",
                        "nocodb": "nocodb"
                    }

                    database_name = database_mapping.get(app_name)
                    if database_name:
                        logger.info(f"Creating PostgreSQL database '{database_name}' for {app_name}")

                        # Get server connection info
                        server_ip = server.get("ip")
                        ssh_key_name = server.get("ssh_key", f"{server_name}_key")
                        ssh_key_path = str(self.ssh_manager.get_private_key_path(ssh_key_name))

                        # Get postgres password
                        postgres_password = config.get("postgres_password")

                        # Create database
                        db_result = self.resolver.create_dependency_resources(
                            parent_app=app_name,
                            dependency="postgres",
                            config={
                                "database": database_name,
                                "password": postgres_password
                            },
                            server_ip=server_ip,
                            ssh_key=ssh_key_path
                        )

                        if db_result.get("success"):
                            logger.info(f"✅ Database '{database_name}' created successfully")
                        else:
                            logger.warning(f"⚠️ Failed to create database: {db_result.get('error')}")
                            # Continue anyway - database might already exist

        # Deploy the app
        result = await self.app_deployer.deploy(server, app_name, config)

        # Save generated passwords to vault for dependency apps
        # This allows dependent apps (like N8N) to retrieve these passwords later
        if result.get("success"):
            if app_name in ["postgres", "redis"]:
                password_key = f"{app_name}_password"
                if password_key in config:
                    self.storage.secrets.set_secret(password_key, config[password_key])
                    logger.info(f"Saved {app_name} password to vault for future use by dependent apps")

        # Configure DNS if successful and Cloudflare is configured
        if result.get("success") and self.cloudflare:
            dns_info = server.get("dns", {})
            if dns_info.get("zone"):
                dns_result = await self.app_deployer.configure_dns(
                    server, app_name, dns_info["zone"]
                )
                result["dns_configured"] = dns_result.get("success", False)

        # Update server state
        if result.get("success"):
            apps = server.get("applications", [])
            if app_name not in apps:
                apps.append(app_name)
                server["applications"] = apps
                self.storage.state.update_server(server_name, server)

        return result

    def list_available_apps(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available applications from the registry

        Args:
            category: Optional category filter

        Returns:
            List of available applications
        """
        return self.app_registry.list_apps(category=category)

    async def delete_app(self, server_name: str, app_name: str) -> Dict[str, Any]:
        """
        Delete an application from a server

        Args:
            server_name: Name of the server
            app_name: Name of the application

        Returns:
            Deletion result
        """
        logger.info(f"Deleting {app_name} from server {server_name}")

        # Get server
        server = self.get_server(server_name)
        if not server:
            return {
                "success": False,
                "error": f"Server {server_name} not found"
            }

        # Initialize Portainer if needed
        if not self.portainer:
            if not self._init_portainer_for_server(server_name):
                return {
                    "success": False,
                    "error": "Failed to initialize Portainer client"
                }

        # Ensure App Deployer is ready
        if not self._ensure_app_deployer():
            return {
                "success": False,
                "error": "Failed to initialize App Deployer"
            }

        # Delete the app
        result = await self.app_deployer.delete_app(server, app_name)

        # Update server state if successful
        if result.get("success"):
            apps = server.get("applications", [])
            if app_name in apps:
                apps.remove(app_name)
                server["applications"] = apps
                self.storage.state.update_server(server_name, server)

        return result


# Compatibility alias for migration period
LivChatSetup = Orchestrator

__all__ = ["Orchestrator", "DependencyResolver", "LivChatSetup"]