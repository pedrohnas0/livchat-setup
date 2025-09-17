"""Tests for providers module"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.providers.base import ProviderInterface
from src.providers.hetzner import HetznerProvider


class TestProviderInterface:
    """Test provider base interface"""

    def test_interface_is_abstract(self):
        """Test that ProviderInterface cannot be instantiated"""
        with pytest.raises(TypeError):
            ProviderInterface()

    def test_interface_methods_defined(self):
        """Test that interface defines required methods"""
        # Check that abstract methods are defined
        assert hasattr(ProviderInterface, 'create_server')
        assert hasattr(ProviderInterface, 'delete_server')
        assert hasattr(ProviderInterface, 'list_servers')
        assert hasattr(ProviderInterface, 'get_server')


class TestHetznerProvider:
    """Test Hetzner Cloud provider"""

    @patch('src.providers.hetzner.Client')
    def test_init_creates_client(self, mock_client_class):
        """Test that init creates Hetzner client"""
        provider = HetznerProvider("test_token")

        mock_client_class.assert_called_once_with(token="test_token")

    @patch('src.providers.hetzner.time.sleep')  # Mock sleep to avoid timeout
    @patch('src.providers.hetzner.Client')
    def test_create_server_success(self, mock_client_class, mock_sleep):
        """Test successful server creation"""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock server object
        mock_server = Mock()
        mock_server.id = 12345
        mock_server.name = "test-server"
        mock_server.status = "running"
        mock_server.public_net = Mock()
        mock_server.public_net.ipv4 = Mock(ip="1.2.3.4")
        mock_server.public_net.ipv6 = Mock(ip="2001:db8::1")
        mock_server.datacenter = Mock(name="nbg1-dc3")

        # Mock response
        mock_response = Mock()
        mock_response.server = mock_server
        mock_response.action = Mock()

        mock_client.servers.create.return_value = mock_response
        mock_client.servers.get_by_id.return_value = mock_server  # For wait_for_ready

        # Create provider and server
        provider = HetznerProvider("test_token")
        result = provider.create_server("test-server", "cx21", "nbg1")

        # Verify result
        assert result["id"] == "12345"
        assert result["name"] == "test-server"
        assert result["ip"] == "1.2.3.4"
        assert result["provider"] == "hetzner"

        # Verify API called correctly
        mock_client.servers.create.assert_called_once()

    @patch('src.providers.hetzner.time.sleep')  # Mock sleep
    @patch('src.providers.hetzner.Client')
    def test_create_server_with_ssh_keys(self, mock_client_class, mock_sleep):
        """Test server creation with SSH keys"""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock server
        mock_server = Mock()
        mock_server.id = 12345
        mock_server.name = "test-server"
        mock_server.status = "running"
        mock_server.public_net = Mock()
        mock_server.public_net.ipv4 = Mock(ip="1.2.3.4")
        mock_server.public_net.ipv6 = None
        mock_server.datacenter = Mock(name="nbg1-dc3")

        mock_response = Mock()
        mock_response.server = mock_server
        mock_client.servers.create.return_value = mock_response
        mock_client.servers.get_by_id.return_value = mock_server  # For wait_for_ready

        # Create server with SSH keys
        provider = HetznerProvider("test_token")
        result = provider.create_server(
            "test-server", "cx21", "nbg1",
            ssh_keys=["my-key"]
        )

        assert result["name"] == "test-server"

    @patch('src.providers.hetzner.Client')
    def test_delete_server_success(self, mock_client_class):
        """Test successful server deletion"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock server
        mock_server = Mock()
        mock_client.servers.get_by_id.return_value = mock_server
        mock_client.servers.delete.return_value = True

        provider = HetznerProvider("test_token")
        result = provider.delete_server("12345")

        assert result is True
        mock_client.servers.get_by_id.assert_called_once_with(12345)  # Note: int
        mock_client.servers.delete.assert_called_once_with(mock_server)

    @patch('src.providers.hetzner.Client')
    def test_delete_nonexistent_server(self, mock_client_class):
        """Test deleting nonexistent server"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.servers.get_by_id.return_value = None

        provider = HetznerProvider("test_token")
        result = provider.delete_server("99999")  # Non-existent ID

        assert result is False

    @patch('src.providers.hetzner.Client')
    def test_list_servers(self, mock_client_class):
        """Test listing servers"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock servers
        mock_server1 = Mock()
        mock_server1.id = 1
        mock_server1.name = "server1"
        mock_server1.status = "running"
        mock_server1.public_net = Mock()
        mock_server1.public_net.ipv4 = Mock(ip="1.1.1.1")
        mock_server1.server_type = Mock(name="cx21")
        mock_server1.datacenter = Mock(name="nbg1")

        mock_server2 = Mock()
        mock_server2.id = 2
        mock_server2.name = "server2"
        mock_server2.status = "stopped"
        mock_server2.public_net = Mock()
        mock_server2.public_net.ipv4 = Mock(ip="2.2.2.2")
        mock_server2.server_type = Mock(name="cx31")
        mock_server2.datacenter = Mock(name="fsn1")

        # Return list directly from get_all()
        mock_client.servers.get_all.return_value = [mock_server1, mock_server2]

        provider = HetznerProvider("test_token")
        result = provider.list_servers()

        assert len(result) == 2
        assert result[0]["name"] == "server1"
        assert result[1]["name"] == "server2"

    @patch('src.providers.hetzner.Client')
    def test_get_server_details(self, mock_client_class):
        """Test getting server details"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock server
        mock_server = Mock()
        mock_server.id = 12345
        mock_server.name = "test-server"
        mock_server.status = "running"
        mock_server.public_net = Mock()
        mock_server.public_net.ipv4 = Mock(ip="1.2.3.4")
        mock_server.public_net.ipv6 = Mock(ip="2001:db8::1")
        mock_server.datacenter = Mock(name="nbg1-dc3")
        mock_server.server_type = Mock(name="cx21")
        mock_server.image = Mock(name="ubuntu-22.04")

        mock_client.servers.get_by_id.return_value = mock_server

        provider = HetznerProvider("test_token")
        result = provider.get_server("12345")

        assert result["id"] == "12345"
        assert result["name"] == "test-server"
        assert result["ip"] == "1.2.3.4"

    @patch('src.providers.hetzner.Client')
    def test_get_nonexistent_server(self, mock_client_class):
        """Test getting nonexistent server raises error"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.servers.get_by_id.return_value = None

        provider = HetznerProvider("test_token")

        with pytest.raises(ValueError) as exc:
            provider.get_server("99999")

        assert "Server 99999 not found" in str(exc.value)

    @patch('src.providers.hetzner.Client')
    def test_get_available_server_types(self, mock_client_class):
        """Test getting available server types"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock server types
        mock_type1 = Mock()
        mock_type1.name = "cx21"
        mock_type1.cores = 2
        mock_type1.memory = 4.0
        mock_type1.disk = 40
        mock_type1.description = "CX21 instance"

        mock_type2 = Mock()
        mock_type2.name = "cx31"
        mock_type2.cores = 2
        mock_type2.memory = 8.0
        mock_type2.disk = 80
        mock_type2.description = "CX31 instance"

        # Return list directly from get_all()
        mock_client.server_types.get_all.return_value = [mock_type1, mock_type2]

        provider = HetznerProvider("test_token")
        result = provider.get_available_server_types()

        assert len(result) == 2
        assert result[0]["name"] == "cx21"
        assert result[0]["memory"] == 4.0

    @patch('src.providers.hetzner.Client')
    def test_get_available_locations(self, mock_client_class):
        """Test getting available locations"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock locations
        mock_loc1 = Mock()
        mock_loc1.name = "nbg1"
        mock_loc1.description = "Nuremberg 1"
        mock_loc1.country = "DE"
        mock_loc1.city = "Nuremberg"

        mock_loc2 = Mock()
        mock_loc2.name = "fsn1"
        mock_loc2.description = "Falkenstein 1"
        mock_loc2.country = "DE"
        mock_loc2.city = "Falkenstein"

        # Return list directly from get_all()
        mock_client.locations.get_all.return_value = [mock_loc1, mock_loc2]

        provider = HetznerProvider("test_token")
        result = provider.get_available_locations()

        assert len(result) == 2
        assert result[0]["name"] == "nbg1"
        assert result[0]["country"] == "DE"

    @patch('src.providers.hetzner.Client')
    def test_get_available_images(self, mock_client_class):
        """Test getting available images"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock images
        mock_img1 = Mock()
        mock_img1.name = "ubuntu-22.04"
        mock_img1.description = "Ubuntu 22.04"
        mock_img1.type = "system"
        mock_img1.os_flavor = "ubuntu"
        mock_img1.os_version = "22.04"

        mock_img2 = Mock()
        mock_img2.name = "debian-12"
        mock_img2.description = "Debian 12"
        mock_img2.type = "system"
        mock_img2.os_flavor = "debian"
        mock_img2.os_version = "12"

        # Mock snapshot to test filtering
        mock_snapshot = Mock()
        mock_snapshot.name = "my-snapshot"
        mock_snapshot.type = "snapshot"

        # Return list directly from get_all()
        mock_client.images.get_all.return_value = [mock_img1, mock_img2, mock_snapshot]

        provider = HetznerProvider("test_token")
        result = provider.get_available_images()

        # Should filter out snapshots
        assert len(result) == 2
        assert result[0]["name"] == "ubuntu-22.04"

    @patch('src.providers.hetzner.Client')
    def test_handle_api_error(self, mock_client_class):
        """Test handling API errors"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock generic exception (hcloud.core.exceptions may not exist)
        mock_client.servers.create.side_effect = Exception("API Error: Invalid token")

        provider = HetznerProvider("invalid_token")

        with pytest.raises(Exception) as exc:
            provider.create_server("test", "cx21", "nbg1")

        assert "Invalid token" in str(exc.value)

    @patch('src.providers.hetzner.time.sleep')  # Correct path for sleep
    @patch('src.providers.hetzner.Client')
    def test_wait_for_server_ready(self, mock_client_class, mock_sleep):
        """Test waiting for server to be ready"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock server that starts as initializing
        mock_server = Mock()
        mock_server.id = 12345
        mock_server.name = "test-server"
        mock_server.status = "initializing"
        mock_server.public_net = Mock()
        mock_server.public_net.ipv4 = Mock(ip="1.2.3.4")
        mock_server.public_net.ipv6 = None
        mock_server.datacenter = Mock(name="nbg1-dc3")

        # Create mock sequence: initializing -> running
        mock_server_ready = Mock()
        mock_server_ready.id = 12345
        mock_server_ready.name = "test-server"
        mock_server_ready.status = "running"
        mock_server_ready.public_net = mock_server.public_net
        mock_server_ready.datacenter = mock_server.datacenter

        mock_response = Mock()
        mock_response.server = mock_server
        mock_client.servers.create.return_value = mock_response

        # First call returns initializing, second returns running
        mock_client.servers.get_by_id.side_effect = [mock_server, mock_server_ready]

        provider = HetznerProvider("test_token")
        result = provider.create_server("test-server", "cx21", "nbg1")

        assert result["status"] == "running"
        assert mock_sleep.called  # Verify sleep was called