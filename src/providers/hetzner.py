"""Hetzner Cloud provider implementation"""

import logging
import time
from typing import Dict, Any, List, Optional

from hcloud import Client
from hcloud.servers.domain import Server
from hcloud.server_types.domain import ServerType
from hcloud.images.domain import Image
from hcloud.locations.domain import Location
from hcloud.ssh_keys.domain import SSHKey

from .base import ProviderInterface

logger = logging.getLogger(__name__)


class HetznerProvider(ProviderInterface):
    """Hetzner Cloud provider"""

    def __init__(self, api_token: str):
        """
        Initialize Hetzner provider

        Args:
            api_token: Hetzner Cloud API token
        """
        self.client = Client(token=api_token)
        logger.info("Hetzner provider initialized")

    def create_server(self, name: str, server_type: str, location: str,
                     image: str = "ubuntu-22.04", ssh_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a new server on Hetzner Cloud

        Args:
            name: Server name
            server_type: Server type (e.g., 'cx21')
            location: Location/region (e.g., 'nbg1')
            image: OS image (default: 'ubuntu-22.04')
            ssh_keys: List of SSH key names (optional)

        Returns:
            Server information dictionary
        """
        logger.info(f"Creating Hetzner server: {name} ({server_type} in {location})")

        try:
            # Get server type
            server_type_obj = ServerType(name=server_type)

            # Get image
            image_obj = Image(name=image)

            # Get location
            location_obj = Location(name=location)

            # Get SSH keys if provided
            ssh_key_objs = []
            if ssh_keys:
                logger.info(f"Looking for SSH keys: {ssh_keys}")

                # First, list all available SSH keys for debugging
                all_keys = self.client.ssh_keys.get_all()
                logger.debug(f"Available SSH keys in Hetzner: {[k.name for k in all_keys]}")

                for key_name in ssh_keys:
                    # Try to get the SSH key from Hetzner by name
                    try:
                        key = self.client.ssh_keys.get_by_name(key_name)
                        if key:
                            ssh_key_objs.append(key)
                            logger.info(f"✅ Found SSH key: {key_name} (ID: {key.id})")
                        else:
                            logger.error(f"❌ SSH key {key_name} not found in Hetzner")
                            # List available keys for debugging
                            logger.error(f"   Available keys: {[k.name for k in all_keys]}")
                    except Exception as e:
                        logger.error(f"❌ Error getting SSH key {key_name}: {e}")
                        logger.error(f"   Available keys: {[k.name for k in all_keys]}")

            if not ssh_key_objs and ssh_keys:
                logger.warning("⚠️ No SSH keys found - server will be created without SSH access!")
                logger.warning("   You may need to use Hetzner console to access the server")

            # Create server
            response = self.client.servers.create(
                name=name,
                server_type=server_type_obj,
                image=image_obj,
                location=location_obj,
                ssh_keys=ssh_key_objs if ssh_key_objs else None,
                start_after_create=True,
            )

            server = response.server
            logger.info(f"Server creation initiated: {server.id}")

            # Wait for server to be ready
            server = self._wait_for_server_ready(server)

            # Get public IP
            public_ip = None
            if server.public_net and server.public_net.ipv4:
                public_ip = server.public_net.ipv4.ip

            server_info = {
                "id": str(server.id),
                "name": server.name,
                "provider": "hetzner",
                "ip": public_ip,
                "ipv6": server.public_net.ipv6.ip if server.public_net and server.public_net.ipv6 else None,
                "type": server_type,
                "region": location,
                "image": image,
                "status": server.status,
                "datacenter": server.datacenter.name if server.datacenter else None,
            }

            logger.info(f"Server created successfully: {name} ({public_ip})")
            return server_info

        except Exception as e:
            logger.error(f"Failed to create server: {e}")
            raise

    def _wait_for_server_ready(self, server: Server, timeout: int = 120) -> Server:
        """
        Wait for server to be ready

        Args:
            server: Server object
            timeout: Timeout in seconds

        Returns:
            Updated server object
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Refresh server status
            server = self.client.servers.get_by_id(server.id)

            if server.status == "running":
                logger.info(f"Server {server.name} is running")
                return server

            logger.debug(f"Server status: {server.status}, waiting...")
            time.sleep(2)

        raise TimeoutError(f"Server {server.name} did not become ready within {timeout} seconds")

    def delete_server(self, server_id: str) -> bool:
        """
        Delete a server

        Args:
            server_id: Server ID

        Returns:
            True if successful
        """
        logger.info(f"Deleting Hetzner server: {server_id}")

        try:
            server = self.client.servers.get_by_id(int(server_id))
            if server:
                self.client.servers.delete(server)
                logger.info(f"Server {server_id} deleted successfully")
                return True
            else:
                logger.warning(f"Server {server_id} not found")
                return False
        except Exception as e:
            logger.error(f"Failed to delete server: {e}")
            raise

    def list_servers(self) -> List[Dict[str, Any]]:
        """
        List all servers

        Returns:
            List of server information
        """
        logger.debug("Listing Hetzner servers")

        try:
            servers = self.client.servers.get_all()
            server_list = []

            for server in servers:
                public_ip = None
                if server.public_net and server.public_net.ipv4:
                    public_ip = server.public_net.ipv4.ip

                server_info = {
                    "id": str(server.id),
                    "name": server.name,
                    "provider": "hetzner",
                    "ip": public_ip,
                    "type": server.server_type.name if server.server_type else None,
                    "status": server.status,
                    "datacenter": server.datacenter.name if server.datacenter else None,
                }
                server_list.append(server_info)

            logger.debug(f"Found {len(server_list)} servers")
            return server_list

        except Exception as e:
            logger.error(f"Failed to list servers: {e}")
            raise

    def get_server(self, server_id: str) -> Dict[str, Any]:
        """
        Get server details

        Args:
            server_id: Server ID

        Returns:
            Server information
        """
        logger.debug(f"Getting Hetzner server: {server_id}")

        try:
            server = self.client.servers.get_by_id(int(server_id))

            if not server:
                raise ValueError(f"Server {server_id} not found")

            public_ip = None
            if server.public_net and server.public_net.ipv4:
                public_ip = server.public_net.ipv4.ip

            server_info = {
                "id": str(server.id),
                "name": server.name,
                "provider": "hetzner",
                "ip": public_ip,
                "ipv6": server.public_net.ipv6.ip if server.public_net and server.public_net.ipv6 else None,
                "type": server.server_type.name if server.server_type else None,
                "status": server.status,
                "datacenter": server.datacenter.name if server.datacenter else None,
                "created": server.created.isoformat() if server.created else None,
            }

            return server_info

        except Exception as e:
            logger.error(f"Failed to get server: {e}")
            raise

    def get_available_server_types(self) -> List[Dict[str, Any]]:
        """
        Get available server types

        Returns:
            List of server types
        """
        server_types = self.client.server_types.get_all()
        return [
            {
                "name": st.name,
                "cores": st.cores,
                "memory": st.memory,
                "disk": st.disk,
                "description": st.description,
            }
            for st in server_types
        ]

    def get_available_locations(self) -> List[Dict[str, Any]]:
        """
        Get available locations

        Returns:
            List of locations
        """
        locations = self.client.locations.get_all()
        return [
            {
                "name": loc.name,
                "description": loc.description,
                "country": loc.country,
                "city": loc.city,
            }
            for loc in locations
        ]

    def get_available_images(self) -> List[Dict[str, Any]]:
        """
        Get available OS images

        Returns:
            List of images
        """
        images = self.client.images.get_all()
        return [
            {
                "name": img.name,
                "description": img.description,
                "os_flavor": img.os_flavor,
                "os_version": img.os_version,
            }
            for img in images
            if img.type == "system"  # Only show OS images, not snapshots
        ]