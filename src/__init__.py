"""LivChat Setup - Automated server setup and application deployment"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from config import ConfigManager
from state import StateManager
from vault import SecretsManager
from providers.hetzner import HetznerProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LivChatSetup:
    """Main orchestrator for LivChat Setup system"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize LivChat Setup

        Args:
            config_dir: Custom config directory (default: ~/.livchat)
        """
        self.config_dir = config_dir or Path.home() / ".livchat"
        self.config = ConfigManager(self.config_dir)
        self.state = StateManager(self.config_dir)
        self.secrets = SecretsManager(self.config_dir)
        self.provider = None

        # Auto-load existing data if available
        if self.config_dir.exists():
            if (self.config_dir / "config.yaml").exists():
                self.config.load_config()
            if (self.config_dir / "state.json").exists():
                self.state.load_state()

        logger.info(f"LivChat Setup initialized with config dir: {self.config_dir}")

    def init(self) -> None:
        """Initialize configuration directory and files"""
        logger.info("Initializing LivChat Setup...")

        # Create config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Initialize managers
        self.config.init()
        self.state.init()
        self.secrets.init()

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
        self.secrets.set_secret(f"{provider_name}_token", token)

        # Update config
        self.config.set("provider", provider_name)

        # Initialize provider
        if provider_name == "hetzner":
            self.provider = HetznerProvider(token)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

        logger.info(f"Provider {provider_name} configured successfully")

    def create_server(self, name: str, server_type: str, region: str) -> Dict[str, Any]:
        """
        Create a new server

        Args:
            name: Server name
            server_type: Server type (e.g., 'cx21')
            region: Region/location (e.g., 'nbg1')

        Returns:
            Server information dictionary
        """
        if not self.provider:
            # Try to load provider from config
            provider_name = self.config.get("provider")
            if provider_name == "hetzner":
                token = self.secrets.get_secret("hetzner_token")
                self.provider = HetznerProvider(token)
            else:
                raise RuntimeError("No provider configured. Run configure_provider first.")

        logger.info(f"Creating server: {name} ({server_type} in {region})")

        # Create server via provider
        server = self.provider.create_server(name, server_type, region)

        # Save to state
        self.state.add_server(name, server)

        logger.info(f"Server {name} created successfully: {server['ip']}")
        return server

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """List all managed servers"""
        return self.state.list_servers()

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """Get server by name"""
        return self.state.get_server(name)

    def delete_server(self, name: str) -> bool:
        """
        Delete a server

        Args:
            name: Server name

        Returns:
            True if successful
        """
        logger.info(f"Deleting server: {name}")

        server = self.state.get_server(name)
        if not server:
            logger.warning(f"Server {name} not found in state")
            return False

        if not self.provider:
            # Try to load provider from config
            provider_name = server.get("provider", self.config.get("provider"))
            if provider_name == "hetzner":
                token = self.secrets.get_secret("hetzner_token")
                self.provider = HetznerProvider(token)

        # Delete from provider
        if self.provider:
            self.provider.delete_server(server["id"])

        # Remove from state
        self.state.remove_server(name)

        logger.info(f"Server {name} deleted successfully")
        return True


__version__ = "0.1.0"
__all__ = ["LivChatSetup", "ConfigManager", "StateManager", "SecretsManager"]