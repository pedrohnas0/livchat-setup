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
        return self.server_manager.create_server(name, server_type, region, image)

    def delete_server(self, name: str) -> bool:
        """Delete a server"""
        return self.server_manager.delete_server(name)

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """List all managed servers"""
        return self.storage.state.list_servers()

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """Get server by name"""
        return self.storage.state.get_server(name)

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
