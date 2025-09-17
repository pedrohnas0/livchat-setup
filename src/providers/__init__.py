"""Cloud providers for LivChat Setup"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class ProviderInterface(ABC):
    """Base interface for cloud providers"""

    @abstractmethod
    def create_server(self, name: str, server_type: str, location: str) -> Dict[str, Any]:
        """Create a new server"""
        pass

    @abstractmethod
    def delete_server(self, server_id: str) -> bool:
        """Delete a server"""
        pass

    @abstractmethod
    def list_servers(self) -> List[Dict[str, Any]]:
        """List all servers"""
        pass

    @abstractmethod
    def get_server(self, server_id: str) -> Dict[str, Any]:
        """Get server details"""
        pass