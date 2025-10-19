"""
ServerManager - Manages server lifecycle (create, list, get, delete)

Extracted from orchestrator.py as part of PLAN-08 refactoring.
"""

import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ServerManager:
    """Manages server lifecycle operations"""

    def __init__(self, storage, ssh_manager, provider_manager):
        """
        Initialize ServerManager

        Args:
            storage: StorageManager instance
            ssh_manager: SSHKeyManager instance
            provider_manager: ProviderManager instance
        """
        self.storage = storage
        self.ssh_manager = ssh_manager
        self.provider_manager = provider_manager

    def create(self, name: str, server_type: str, region: str,
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

        Raises:
            RuntimeError: If SSH key cannot be added to provider
        """
        logger.info(f"Creating server: {name} ({server_type} in {region} with {image})")

        # Generate SSH key name
        key_name = f"{name}_key"

        # Check if SSH key exists locally
        logger.debug(f"Checking if SSH key exists: {key_name}")
        key_exists = self.ssh_manager.key_exists(key_name)
        logger.debug(f"SSH key {key_name} exists locally: {key_exists}")

        # Generate key if it doesn't exist locally
        if not key_exists:
            logger.info(f"Generating SSH key for {name}")
            key_info = self.ssh_manager.generate_key_pair(key_name)
            logger.info(f"SSH key generated: {key_name}")

        # Get Hetzner token to add SSH key
        token = self.storage.secrets.get_secret("hetzner_token")
        if not token:
            logger.error("No Hetzner token available to add SSH key")
            raise RuntimeError("Cannot add SSH key without Hetzner token")

        # Always ensure the key is added to Hetzner
        logger.info(f"Ensuring SSH key {key_name} is added to Hetzner...")
        success = self.ssh_manager.add_to_hetzner(key_name, token)
        if not success:
            logger.error(f"L Failed to add SSH key {key_name} to Hetzner")
            raise RuntimeError(f"Cannot add SSH key to Hetzner - server would be inaccessible")
        else:
            logger.info(f" SSH key {key_name} is available in Hetzner")
            # Small delay to ensure key is available
            time.sleep(2)

        # Get provider instance
        provider = self.provider_manager.get_provider()

        # Create server with SSH key
        server = provider.create_server(name, server_type, region,
                                       image=image, ssh_keys=[key_name])

        # Add SSH key info to server data
        server["ssh_key"] = key_name

        # Save to state
        self.storage.state.add_server(name, server)

        logger.info(f"Server {name} created successfully: {server.get('ip', 'N/A')}")
        return server

    def list(self) -> Dict[str, Dict[str, Any]]:
        """
        List all managed servers

        Returns:
            Dictionary of all servers
        """
        return self.storage.state.list_servers()

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get server by name

        Args:
            name: Server name

        Returns:
            Server data or None if not found
        """
        return self.storage.state.get_server(name)

    def delete(self, name: str) -> bool:
        """
        Delete a server

        Args:
            name: Server name

        Returns:
            True if successful, False if server not found
        """
        logger.info(f"Deleting server: {name}")

        # Check if server exists in state
        server = self.storage.state.get_server(name)
        if not server:
            logger.warning(f"Server {name} not found in state")
            return False

        # Get provider instance
        provider = self.provider_manager.get_provider()

        # Delete from provider if server has ID
        if provider and "id" in server:
            try:
                provider.delete_server(server["id"])
                logger.info(f"Server {name} deleted from provider")
            except Exception as e:
                logger.error(f"Failed to delete server from provider: {e}")
                # Continue with state removal even if provider deletion fails

        # Remove from state
        self.storage.state.remove_server(name)
        logger.info(f"Server {name} removed from state")

        return True
