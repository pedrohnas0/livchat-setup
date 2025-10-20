"""
Core Orchestrator - Facade pattern for all orchestration operations

This is the main entry point that coordinates all managers (PLAN-08 refactoring)
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from ..storage import StorageManager
    from ..ssh_manager import SSHKeyManager
    from ..app_registry import AppRegistry
    from ..integrations.cloudflare import CloudflareClient
    from ..integrations.portainer import PortainerClient
    from ..ansible_executor import AnsibleRunner
    from ..server_setup import ServerSetup
    from .provider_manager import ProviderManager
    from .server_manager import ServerManager
    from .deployment_manager import DeploymentManager
    from .dns_manager import DNSManager
except ImportError:
    from storage import StorageManager
    from ssh_manager import SSHKeyManager
    from app_registry import AppRegistry
    from integrations.cloudflare import CloudflareClient
    from integrations.portainer import PortainerClient
    from ansible_executor import AnsibleRunner
    from server_setup import ServerSetup
    from provider_manager import ProviderManager
    from server_manager import ServerManager
    from deployment_manager import DeploymentManager
    from dns_manager import DNSManager

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main orchestrator - coordinates all managers via Facade pattern

    Delegates to specialized managers:
    - ProviderManager: Cloud provider operations
    - ServerManager: Server CRUD operations
    - DeploymentManager: Application deployments
    - DNSManager: DNS configuration
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize Orchestrator

        Args:
            config_dir: Custom config directory (default: ~/.livchat)
        """
        self.config_dir = config_dir or Path.home() / ".livchat"

        # Core components
        self.storage = StorageManager(self.config_dir)
        self.ssh_manager = SSHKeyManager(self.storage)
        self.app_registry = AppRegistry()

        # Load app definitions from apps/definitions directory
        apps_dir = Path(__file__).parent.parent.parent / "apps" / "definitions"
        if apps_dir.exists():
            logger.info(f"Loading app definitions from {apps_dir}")
            self.app_registry.load_definitions(str(apps_dir))
        else:
            logger.warning(f"App definitions directory not found: {apps_dir}")

        # Infrastructure components (for server setup)
        self.ansible_runner = AnsibleRunner(self.ssh_manager)
        self.server_setup = ServerSetup(self.ansible_runner, self.storage)

        # Integration clients (lazy initialized)
        self.cloudflare = None
        self.portainer = None

        # Managers (initialized immediately)
        self.provider_manager = ProviderManager(
            storage=self.storage,
            ssh_manager=self.ssh_manager
        )

        self.server_manager = ServerManager(
            storage=self.storage,
            ssh_manager=self.ssh_manager,
            provider_manager=self.provider_manager
        )

        self.deployment_manager = DeploymentManager(
            storage=self.storage,
            app_registry=self.app_registry,
            ssh_manager=self.ssh_manager
        )

        self.dns_manager = DNSManager(
            storage=self.storage
        )

        # Try to initialize Cloudflare from saved config
        self._init_cloudflare_from_config()

        logger.info("Orchestrator initialized with modular architecture")

    # ==================== INITIALIZATION ====================

    def init(self) -> None:
        """Initialize configuration directory and files"""
        logger.info("Initializing LivChat Setup...")
        self.storage.init()

    # ==================== INTEGRATION CONFIGURATION ====================

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
                self.dns_manager.cloudflare = self.cloudflare
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

            # Share with DNS manager
            self.dns_manager.cloudflare = self.cloudflare

            # Save credentials securely in vault
            self.storage.secrets.set_secret("cloudflare_email", email)
            self.storage.secrets.set_secret("cloudflare_api_key", api_key)

            logger.info("Cloudflare configured successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to configure Cloudflare: {e}")
            self.cloudflare = None
            return False

    def _init_portainer_for_server(self, server_name: str) -> bool:
        """
        Initialize Portainer client for a specific server

        Args:
            server_name: Name of the server

        Returns:
            True if initialized successfully
        """
        # OPTIMIZATION: Reuse existing PortainerClient if already configured
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

        if not portainer_password:
            logger.error(f"Portainer password not found in vault for {server_name}")
            return False

        try:
            # Initialize Portainer client
            self.portainer = PortainerClient(
                url=f"https://{server_ip}:9443",
                username="admin",
                password=portainer_password
            )

            # Share with deployment manager
            self.deployment_manager.portainer = self.portainer

            logger.info(f"Portainer client initialized for server {server_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Portainer client: {e}")
            return False

    # ==================== PROVIDER OPERATIONS (delegated) ====================

    def configure_provider(self, provider_name: str, token: str) -> None:
        """Configure cloud provider credentials"""
        self.provider_manager.configure_provider(provider_name, token)

    # ==================== SERVER OPERATIONS (delegated) ====================

    def create_server(self, name: str, server_type: str, region: str,
                     image: str = "ubuntu-22.04") -> Dict[str, Any]:
        """Create a new server"""
        return self.server_manager.create(name, server_type, region, image)

    def delete_server(self, name: str) -> bool:
        """Delete a server"""
        return self.server_manager.delete(name)

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """List all managed servers"""
        return self.server_manager.list()

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """Get server by name"""
        return self.server_manager.get(name)

    # ==================== DNS OPERATIONS (delegated) ====================

    async def setup_dns_for_server(self, server_name: str, zone_name: str,
                                  subdomain: Optional[str] = None) -> Dict[str, Any]:
        """Setup DNS records for a server"""
        return await self.dns_manager.setup_dns_for_server(server_name, zone_name, subdomain)

    async def add_app_dns(self, app_name: str, zone_name: str,
                        subdomain: Optional[str] = None) -> Dict[str, Any]:
        """Add DNS records for an application"""
        return await self.dns_manager.add_app_dns(app_name, zone_name, subdomain)

    # ==================== DEPLOYMENT OPERATIONS (delegated) ====================

    async def deploy_app(self, server_name: str, app_name: str,
                        config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Deploy an application with automatic dependency resolution

        Before deploying, initializes Portainer for the server
        """
        # Initialize Portainer for this server
        if not self._init_portainer_for_server(server_name):
            return {
                "success": False,
                "error": "Failed to initialize Portainer client"
            }

        # Update deployment manager with clients
        self.deployment_manager.portainer = self.portainer
        self.deployment_manager.cloudflare = self.cloudflare

        return await self.deployment_manager.deploy_app(server_name, app_name, config)

    def list_available_apps(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available applications from the registry"""
        return self.app_registry.list_apps(category=category)

    # ==================== RESOURCE MANAGEMENT (delegated) ====================

    def create_dependency_resources(self, parent_app: str, dependency: str,
                                   config: Dict[str, Any], server_ip: str,
                                   ssh_key: str) -> Dict[str, Any]:
        """Create dependency resources (e.g., PostgreSQL databases)"""
        return self.deployment_manager.create_dependency_resources(
            parent_app, dependency, config, server_ip, ssh_key
        )

    # ==================== INFRASTRUCTURE OPERATIONS (thin wrappers) ====================

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

        # Deploy Portainer via server_setup
        result = self.server_setup.deploy_portainer(server, config or {})

        if result.success:
            logger.info(f"Portainer deployed successfully on {server_name}")

            # NOTE: State update removed - infrastructure_executor handles adding "infrastructure" to state
            # This prevents duplication when portainer is deployed as part of infrastructure bundle

            # Automatic Portainer initialization
            logger.info("Initializing Portainer admin account...")

            # Get server IP
            server_ip = server.get("ip")

            # Get credentials from vault (should have been saved during deployment)
            portainer_password = self.storage.secrets.get_secret(f"portainer_password_{server_name}")

            if not portainer_password:
                logger.error(f"Portainer password not found in vault for {server_name}")
                logger.error("This indicates a problem during deployment")
                return False

            # Create Portainer client and SAVE to self.portainer for reuse
            # This avoids creating multiple clients with different states
            self.portainer = PortainerClient(
                url=f"https://{server_ip}:9443",
                username="admin",
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
                    logger.info(f"   Username: admin")
                    logger.info(f"   Password stored in vault: portainer_password_{server_name}")
                    logger.info(f"   PortainerClient saved to orchestrator for reuse")
                else:
                    logger.warning("Portainer admin initialization returned false (may already be initialized)")
            else:
                logger.error("Portainer did not become ready within timeout period")
                return False

        return result.success

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

        # Verify SSH key is configured (created during server creation)
        if not server.get("ssh_key"):
            logger.error(f"Server {server_name} has no SSH key configured")
            return {
                "success": False,
                "message": "Server has no SSH key configured",
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
            "dns_config": dns_config
        }
