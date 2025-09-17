"""Base provider interface for LivChat Setup"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class ProviderInterface(ABC):
    """Base interface for cloud providers"""

    @abstractmethod
    def create_server(self, name: str, server_type: str, location: str) -> Dict[str, Any]:
        """
        Create a new server

        Args:
            name: Server name
            server_type: Server type/size
            location: Location/region

        Returns:
            Server information dictionary
        """
        pass

    @abstractmethod
    def delete_server(self, server_id: str) -> bool:
        """
        Delete a server

        Args:
            server_id: Server ID

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def list_servers(self) -> List[Dict[str, Any]]:
        """
        List all servers

        Returns:
            List of server dictionaries
        """
        pass

    @abstractmethod
    def get_server(self, server_id: str) -> Dict[str, Any]:
        """
        Get server details

        Args:
            server_id: Server ID

        Returns:
            Server information dictionary
        """
        pass