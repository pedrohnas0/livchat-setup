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
                # Save DNS config to state (only zone and subdomain) - v0.2.0
                dns_config = {
                    "zone_name": zone_name,
                    "subdomain": subdomain
                }
                server["dns_config"] = dns_config
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

    def create_dependency_resources(self, parent_app: str, dependency: str,
                                   config: Dict[str, Any],
                                   server_ip: str, ssh_key: str) -> Dict[str, Any]:
        """
        Create actual resources for a dependency (e.g., PostgreSQL database)

        This creates RESOURCES (like databases) inside already-deployed apps.
        It does NOT install the dependency app itself.

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
                # Find postgres container name in swarm (with retry)
                container_name = None
                max_retries = 5
                retry_delay = 3

                for attempt in range(max_retries):
                    find_container_cmd = [
                        "ssh", "-i", ssh_key,
                        "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=/dev/null",
                        f"root@{server_ip}",
                        # Use service-specific name pattern for Swarm
                        "docker ps --filter name=postgres_postgres --format '{{.Names}}' | head -1"
                    ]

                    container_result = subprocess.run(
                        find_container_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                    if container_result.returncode == 0:
                        container_name = container_result.stdout.strip()
                        if container_name:
                            logger.info(f"Found postgres container: {container_name}")
                            break

                    if attempt < max_retries - 1:
                        logger.info(f"Container not ready yet, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                        import time
                        time.sleep(retry_delay)

                if not container_name:
                    return {
                        "success": False,
                        "error": "Postgres container not found after multiple retries. Container may not be running yet."
                    }

                logger.info(f"✅ Postgres container ready: {container_name}")

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

    def setup_server(self, server_name: str, zone_name: str,
                    subdomain: Optional[str] = None,
                    config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run complete server setup with mandatory DNS configuration (v0.2.0)

        Args:
            server_name: Name of the server
            zone_name: Cloudflare zone (REQUIRED - ex: 'livchat.ai')
            subdomain: Optional subdomain (ex: 'lab', 'prod')
            config: Optional configuration overrides

        Returns:
            Setup result with DNS configuration

        Raises:
            ValueError: If server not found or Cloudflare not configured
        """
        server = self.get_server(server_name)
        if not server:
            raise ValueError(f"Server {server_name} not found")

        logger.info(f"Starting setup for server {server_name} with DNS: {zone_name}")

        # v0.2.0: Validate Cloudflare credentials BEFORE setup
        cf_email = self.storage.secrets.get_secret("cloudflare_email")
        cf_api_key = self.storage.secrets.get_secret("cloudflare_api_key")
        if not cf_email or not cf_api_key:
            raise ValueError(
                "Cloudflare credentials not configured. "
                "Run manage-secrets to set cloudflare_email and cloudflare_api_key first."
            )

        logger.info(f"Cloudflare credentials validated for {server_name}")

        # v0.2.0: Save DNS config to state BEFORE setup
        dns_config = {"zone_name": zone_name}
        if subdomain:
            dns_config["subdomain"] = subdomain

        server["dns_config"] = dns_config
        self.storage.state.update_server(server_name, server)
        logger.info(f"DNS configured for {server_name}: {dns_config}")

        # Ensure SSH key is configured
        if not self.setup_server_ssh(server_name):
            return {
                "success": False,
                "message": "Failed to setup SSH key",
                "server": server_name,
                "dns_config": dns_config
            }

        # Run full setup through ServerSetup (no Traefik/Portainer anymore)
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
            "details": result.details,
            "dns_config": dns_config  # v0.2.0: Include DNS in response
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

            # Create Portainer client and SAVE to self.portainer for reuse
            # This avoids creating multiple clients with different states
            # NOTE: Portainer initial admin is always 'admin', we can update later via API
            self.portainer = PortainerClient(
                url=f"https://{server_ip}:9443",
                username="admin",  # Portainer requires 'admin' for initial setup
                password=portainer_password
            )

            # Wait for Portainer to be ready
            import asyncio
            ready = asyncio.run(self.portainer.wait_for_ready(max_attempts=30, delay=10))

            if ready:
                # Initialize admin account
                initialized = asyncio.run(self.portainer.initialize_admin())

                if initialized:
                    logger.info(f"✅ Portainer admin initialized successfully!")
                    logger.info(f"   Access URL: https://{server_ip}:9443")
                    logger.info(f"   Username: {admin_email}")
                    logger.info(f"   Password stored in vault: portainer_password_{server_name}")
                    logger.info(f"   PortainerClient saved to orchestrator for reuse")
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
        # OPTIMIZATION: Reuse existing PortainerClient if already configured
        # This avoids creating multiple clients and potential race conditions
        if self.portainer:
            logger.info(f"Reusing existing PortainerClient for {server_name}")
            return True

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
        Deploy an application to a server with automatic dependency installation (v0.2.0)

        This method now automatically installs missing dependencies, just like npm/apt/pip!

        Args:
            server_name: Name of the server
            app_name: Name of the application
            config: Optional deployment configuration

        Returns:
            Deployment result with dependency info

        Example:
            >>> orchestrator.deploy_app("server", "n8n")
            # Automatically installs: postgres → redis → n8n
        """
        logger.info(f"🚀 Deploying {app_name} to server {server_name}")

        # Get server
        server = self.get_server(server_name)
        if not server:
            return {
                "success": False,
                "error": f"Server {server_name} not found"
            }

        # v0.2.0: Resolve dependencies using AppRegistry (YAML-based)
        try:
            install_order = self.app_registry.resolve_dependencies(app_name)
            logger.info(f"📦 Dependency resolution: {' → '.join(install_order)}")
        except ValueError as e:
            return {
                "success": False,
                "error": f"Dependency resolution failed: {str(e)}"
            }

        # Get already-installed apps
        installed_apps = set(server.get("applications", []))
        logger.info(f"✅ Already installed: {installed_apps or 'none'}")

        # Filter out already-installed apps
        apps_to_install = [app for app in install_order if app not in installed_apps]

        if not apps_to_install:
            logger.info(f"✅ {app_name} already deployed!")
            return {
                "success": True,
                "app": app_name,
                "message": "Application already deployed",
                "skipped": True
            }

        logger.info(f"📥 Installing: {' → '.join(apps_to_install)}")

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

        # Auto-install missing dependencies
        installed_in_this_run = []
        for current_app in apps_to_install:
            logger.info(f"🔧 Installing {current_app}...")

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

            # v0.2.0: Build domain from DNS config and app's dns_prefix
            if app_def and "dns_prefix" in app_def:
                dns_config = server.get("dns_config", {})
                zone_name = dns_config.get("zone_name")
                subdomain = dns_config.get("subdomain")

                if zone_name:
                    dns_prefix = app_def["dns_prefix"]

                    # Build domain: {dns_prefix}.{subdomain}.{zone_name} or {dns_prefix}.{zone_name}
                    if subdomain:
                        domain = f"{dns_prefix}.{subdomain}.{zone_name}"
                    else:
                        domain = f"{dns_prefix}.{zone_name}"

                    app_config["domain"] = domain
                    logger.info(f"Built domain for {current_app}: {domain}")

                    # Build additional DNS domains (e.g., webhook_domain for N8N)
                    if "additional_dns" in app_def:
                        for additional in app_def["additional_dns"]:
                            additional_prefix = additional.get("prefix")
                            if additional_prefix:
                                if subdomain:
                                    additional_domain = f"{additional_prefix}.{subdomain}.{zone_name}"
                                else:
                                    additional_domain = f"{additional_prefix}.{zone_name}"

                                # Use prefix as key (e.g., "whk" → "webhook_domain")
                                # Convention: "whk" prefix → "webhook_domain"
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

            # Create dependency resources (e.g., PostgreSQL databases) BEFORE deploying
            if app_def and "dependencies" in app_def:
                for dep in app_def["dependencies"]:
                    if dep == "postgres":
                        # Database name mapping
                        database_mapping = {
                            "n8n": "n8n_queue",
                            "chatwoot": "chatwoot_production",
                            "grafana": "grafana",
                            "nocodb": "nocodb"
                        }

                        database_name = database_mapping.get(current_app)
                        if database_name:
                            logger.info(f"Creating PostgreSQL database '{database_name}' for {current_app}")

                            server_ip = server.get("ip")
                            ssh_key_name = server.get("ssh_key", f"{server_name}_key")
                            ssh_key_path = str(self.ssh_manager.get_private_key_path(ssh_key_name))

                            postgres_password = app_config.get("postgres_password")

                            # Create database using our method (not self.resolver anymore!)
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
                                logger.info(f"✅ Database '{database_name}' created successfully")
                            else:
                                logger.warning(f"⚠️ Failed to create database: {db_result.get('error')}")

            # Deploy the current app
            result = await self.app_deployer.deploy(server, current_app, app_config)

            if not result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to deploy dependency '{current_app}': {result.get('error')}",
                    "installed_before_failure": installed_in_this_run
                }

            # Save generated passwords to vault for dependency apps
            if current_app in ["postgres", "redis"]:
                password_key = f"{current_app}_password"
                if password_key in app_config:
                    self.storage.secrets.set_secret(password_key, app_config[password_key])
                    logger.info(f"Saved {current_app} password to vault for future use")

                # Wait for database containers to be fully ready before proceeding
                logger.info(f"⏳ Waiting for {current_app} container to be fully ready...")
                import time
                time.sleep(15)  # Give container time to initialize and become healthy
                logger.info(f"✅ {current_app} should be ready now")

            # Configure DNS if successful and Cloudflare is configured
            if self.cloudflare:
                dns_config = server.get("dns_config", {})
                if dns_config.get("zone_name"):
                    dns_result = await self.app_deployer.configure_dns(
                        server, current_app, dns_config["zone_name"]
                    )
                    if dns_result.get("success"):
                        logger.info(f"✅ DNS configured for {current_app}")

            # Update server state
            apps = server.get("applications", [])
            if current_app not in apps:
                apps.append(current_app)
                server["applications"] = apps
                self.storage.state.update_server(server_name, server)

            installed_in_this_run.append(current_app)
            logger.info(f"✅ {current_app} deployed successfully!")

        return {
            "success": True,
            "app": app_name,
            "message": f"Successfully deployed {app_name} with dependencies",
            "dependencies_resolved": install_order,
            "apps_installed": installed_in_this_run,
            "already_installed": list(installed_apps)
        }

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

__all__ = ["Orchestrator", "LivChatSetup"]